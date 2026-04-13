"""Tests for `RetryingLLMProvider`."""
from __future__ import annotations

import pytest

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider, ILogger, IRetryPolicy
from src.infrastructure.llm.decorators import RetryingLLMProvider
from src.infrastructure.logging import NullLogger


class _FlakyProvider(ILLMProvider):
    """Fails `fail_count` times then returns `poem`."""

    def __init__(self, fail_count: int, poem: str = "result") -> None:
        self._fail_count = fail_count
        self._poem = poem
        self.generate_calls: int = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        if self._fail_count > 0:
            self._fail_count -= 1
            raise LLMError("transient")
        return self._poem

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self.generate("")


class _FixedPolicy(IRetryPolicy):
    """Retry `max_retries` times with a small non-zero delay so sleeps are observable."""

    def __init__(self, max_retries: int, delay_sec: float = 0.01) -> None:
        self._max = max_retries
        self._delay = delay_sec

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        return isinstance(exc, LLMError) and attempt <= self._max

    def next_delay_sec(self, attempt: int) -> float:
        return self._delay


class _NoRetryPolicy(IRetryPolicy):
    def should_retry(self, attempt: int, exc: Exception) -> bool:
        return False

    def next_delay_sec(self, attempt: int) -> float:
        return 0.0


def _make_logger() -> ILogger:
    return NullLogger()


class TestRetryingLLMProvider:
    def test_success_on_first_attempt(self) -> None:
        inner = _FlakyProvider(fail_count=0, poem="ok")
        provider = RetryingLLMProvider(
            inner=inner, policy=_FixedPolicy(3), logger=_make_logger(),
        )
        assert provider.generate("prompt") == "ok"
        assert inner.generate_calls == 1

    def test_success_after_transient_failures(self) -> None:
        inner = _FlakyProvider(fail_count=2, poem="final")
        sleeps: list[float] = []
        provider = RetryingLLMProvider(
            inner=inner,
            policy=_FixedPolicy(3),
            logger=_make_logger(),
            sleep_fn=sleeps.append,
        )
        assert provider.generate("prompt") == "final"
        assert inner.generate_calls == 3
        assert sleeps == [0.01, 0.01]

    def test_error_propagated_when_policy_says_stop(self) -> None:
        inner = _FlakyProvider(fail_count=10, poem="unused")
        provider = RetryingLLMProvider(
            inner=inner,
            policy=_NoRetryPolicy(),
            logger=_make_logger(),
        )
        with pytest.raises(LLMError):
            provider.generate("prompt")
        assert inner.generate_calls == 1
