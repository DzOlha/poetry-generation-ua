"""Tests for `SanitizingLLMProvider`."""
from __future__ import annotations

import pytest

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider, IPoemOutputSanitizer
from src.infrastructure.llm.decorators import SanitizingLLMProvider
from src.infrastructure.tracing import InMemoryLLMCallRecorder, NullLLMCallRecorder


class _StubProvider(ILLMProvider):
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.regen_calls: list[tuple[str, list[str]]] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        self.regen_calls.append((poem, list(feedback)))
        return self.response


class _UppercasingSanitizer(IPoemOutputSanitizer):
    def sanitize(self, text: str) -> str:
        return text.upper()


class _DroppingSanitizer(IPoemOutputSanitizer):
    """Mimics a sanitizer that classifies everything as garbage."""

    def sanitize(self, text: str) -> str:
        return ""


def _make(
    inner: _StubProvider, sanitizer: IPoemOutputSanitizer,
) -> SanitizingLLMProvider:
    return SanitizingLLMProvider(
        inner=inner, sanitizer=sanitizer, recorder=NullLLMCallRecorder(),
    )


class TestSanitizingLLMProvider:
    def test_generate_passes_prompt_and_sanitizes_output(self) -> None:
        inner = _StubProvider(response="hello")
        provider = _make(inner, _UppercasingSanitizer())
        assert provider.generate("prompt-x") == "HELLO"
        assert inner.prompts == ["prompt-x"]

    def test_regenerate_lines_passes_args_and_sanitizes_output(self) -> None:
        inner = _StubProvider(response="poem out")
        provider = _make(inner, _UppercasingSanitizer())
        assert provider.regenerate_lines("poem in", ["fb-1", "fb-2"]) == "POEM OUT"
        assert inner.regen_calls == [("poem in", ["fb-1", "fb-2"])]

    def test_generate_raises_when_sanitizer_returns_empty(self) -> None:
        # When the whole response is garbage the sanitizer returns "" —
        # the decorator must raise so the retry layer gets another turn
        # rather than let the empty string poison the pipeline.
        inner = _StubProvider(response="pure reasoning, no poem")
        provider = _make(inner, _DroppingSanitizer())
        with pytest.raises(LLMError, match="no valid poem lines"):
            provider.generate("prompt-x")

    def test_regenerate_lines_raises_when_sanitizer_returns_empty(self) -> None:
        inner = _StubProvider(response="pure reasoning")
        provider = _make(inner, _DroppingSanitizer())
        with pytest.raises(LLMError, match="no valid poem lines"):
            provider.regenerate_lines("p", ["f"])

    def test_records_sanitized_output_even_when_empty(self) -> None:
        inner = _StubProvider(response="garbage")
        recorder = InMemoryLLMCallRecorder()
        provider = SanitizingLLMProvider(
            inner=inner, sanitizer=_DroppingSanitizer(), recorder=recorder,
        )
        with pytest.raises(LLMError):
            provider.generate("p")
        # Empty string is the signal that sanitizer dropped everything —
        # the trace must reflect that, not silently skip the recording.
        assert recorder.snapshot().sanitized == ""
