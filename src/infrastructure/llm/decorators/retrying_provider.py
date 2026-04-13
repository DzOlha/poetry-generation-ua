"""`RetryingLLMProvider` — adds automatic retries to any `ILLMProvider`.

Wraps an inner provider and delegates retry policy to `IRetryPolicy`. The
decorator itself contains no timing or attempt-count policy — just the
control flow. This keeps the policy unit-testable in isolation and lets
callers compose different strategies (exponential backoff, deadline-based,
never-retry) without touching the decorator.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider, ILogger, IRetryPolicy


class RetryingLLMProvider(ILLMProvider):
    """Retries transient `LLMError` failures according to the injected policy."""

    def __init__(
        self,
        inner: ILLMProvider,
        policy: IRetryPolicy,
        logger: ILogger,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._logger: ILogger = logger
        # Injectable sleep so tests can verify backoff without actually waiting.
        self._sleep = sleep_fn

    def generate(self, prompt: str) -> str:
        return self._retry(lambda: self._inner.generate(prompt), op="generate")

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self._retry(
            lambda: self._inner.regenerate_lines(poem, feedback),
            op="regenerate_lines",
        )

    def _retry(self, call: Callable[[], str], *, op: str) -> str:
        attempt = 0
        while True:
            attempt += 1
            try:
                return call()
            except LLMError as exc:
                if not self._policy.should_retry(attempt, exc):
                    self._logger.error(
                        "LLM call failed after retries",
                        op=op,
                        attempts=attempt,
                        error=str(exc),
                    )
                    raise
                delay = self._policy.next_delay_sec(attempt)
                self._logger.warning(
                    "retrying LLM call",
                    op=op,
                    attempt=attempt,
                    delay_sec=round(delay, 3),
                    error=str(exc),
                )
                if delay > 0:
                    self._sleep(delay)
