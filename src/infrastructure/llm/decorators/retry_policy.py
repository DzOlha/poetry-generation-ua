"""`IRetryPolicy` implementations used by `RetryingLLMProvider`.

`ExponentialBackoffRetry` is the production default: retry up to N times on
any `LLMError`, with a doubling delay capped at `max_delay_sec`. The class
is also trivially usable from tests — pass `max_attempts=1` to disable
retries, or inject a custom `IRetryPolicy` double to observe calls.
"""
from __future__ import annotations

from src.domain.errors import LLMError
from src.domain.ports import IRetryPolicy


class ExponentialBackoffRetry(IRetryPolicy):
    """Retry on LLMError with exponential backoff and a fixed max attempt count.

    Args:
        max_attempts:   Total attempts allowed, including the first one.
                        `max_attempts=1` disables retries entirely.
        base_delay_sec: Delay after the first failure (seconds).
        max_delay_sec:  Upper bound on the delay after N failures.
        multiplier:     Delay multiplier between consecutive failures.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_sec: float = 1.0,
        max_delay_sec: float = 10.0,
        multiplier: float = 2.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if base_delay_sec < 0:
            raise ValueError("base_delay_sec must be >= 0")
        if multiplier <= 0:
            raise ValueError("multiplier must be > 0")
        self._max_attempts = max_attempts
        self._base = base_delay_sec
        self._max_delay = max_delay_sec
        self._multiplier = multiplier

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        if not isinstance(exc, LLMError):
            return False
        return attempt < self._max_attempts

    def next_delay_sec(self, attempt: int) -> float:
        # attempt is 1-based; after the first failure we waited base_delay_sec,
        # after the second we waited base * multiplier, and so on.
        raw = self._base * (self._multiplier ** max(0, attempt - 1))
        return min(raw, self._max_delay)
