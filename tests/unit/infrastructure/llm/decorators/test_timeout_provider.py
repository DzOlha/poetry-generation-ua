"""Tests for `TimeoutLLMProvider`."""
from __future__ import annotations

import time

import pytest

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider
from src.infrastructure.llm.decorators import TimeoutLLMProvider


class _SleepyProvider(ILLMProvider):
    """Sleeps for `delay_sec` before returning."""

    def __init__(self, delay_sec: float, poem: str = "result") -> None:
        self._delay = delay_sec
        self._poem = poem

    def generate(self, prompt: str) -> str:
        time.sleep(self._delay)
        return self._poem

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        time.sleep(self._delay)
        return self._poem


class TestTimeoutLLMProvider:
    def test_fast_call_returns_normally(self) -> None:
        inner = _SleepyProvider(delay_sec=0.0)
        provider = TimeoutLLMProvider(inner=inner, timeout_sec=1.0)
        assert provider.generate("prompt") == "result"

    def test_slow_call_raises_llm_error(self) -> None:
        inner = _SleepyProvider(delay_sec=0.5)
        provider = TimeoutLLMProvider(inner=inner, timeout_sec=0.1)
        with pytest.raises(LLMError, match="timeout"):
            provider.generate("prompt")

    def test_zero_or_negative_timeout_rejected(self) -> None:
        inner = _SleepyProvider(delay_sec=0.0)
        with pytest.raises(ValueError):
            TimeoutLLMProvider(inner=inner, timeout_sec=0.0)
        with pytest.raises(ValueError):
            TimeoutLLMProvider(inner=inner, timeout_sec=-1.0)
