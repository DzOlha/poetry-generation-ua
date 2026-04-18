"""Tests for `ExtractingLLMProvider`."""
from __future__ import annotations

from src.domain.ports import ILLMProvider, IPoemExtractor
from src.infrastructure.llm.decorators import ExtractingLLMProvider
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


class _WrappedExtractor(IPoemExtractor):
    """Returns content between [[ and ]] or the input unchanged."""

    def extract(self, text: str) -> str:
        if "[[" in text and "]]" in text:
            return text.split("[[", 1)[1].split("]]", 1)[0]
        return text


def _make(inner: _StubProvider) -> ExtractingLLMProvider:
    return ExtractingLLMProvider(
        inner=inner,
        extractor=_WrappedExtractor(),
        recorder=NullLLMCallRecorder(),
    )


class TestExtractingLLMProvider:
    def test_generate_peels_envelope(self) -> None:
        inner = _StubProvider(response="CoT [[poem]] epilogue")
        provider = _make(inner)
        assert provider.generate("prompt-x") == "poem"
        assert inner.prompts == ["prompt-x"]

    def test_regenerate_lines_peels_envelope(self) -> None:
        inner = _StubProvider(response="reasoning [[fixed poem]] tail")
        provider = _make(inner)
        assert provider.regenerate_lines("poem in", ["fb"]) == "fixed poem"
        assert inner.regen_calls == [("poem in", ["fb"])]

    def test_missing_envelope_passes_response_through(self) -> None:
        # When tags are missing the extractor must not swallow the response —
        # downstream sanitizer still needs something to work on.
        inner = _StubProvider(response="Тихо спить\nЛіхтарі\n")
        provider = _make(inner)
        assert provider.generate("p") == "Тихо спить\nЛіхтарі\n"

    def test_records_raw_and_extracted_to_recorder(self) -> None:
        inner = _StubProvider(response="CoT [[final poem]] epilogue")
        recorder = InMemoryLLMCallRecorder()
        provider = ExtractingLLMProvider(
            inner=inner, extractor=_WrappedExtractor(), recorder=recorder,
        )
        provider.generate("p")
        snap = recorder.snapshot()
        assert snap.raw == "CoT [[final poem]] epilogue"
        assert snap.extracted == "final poem"
