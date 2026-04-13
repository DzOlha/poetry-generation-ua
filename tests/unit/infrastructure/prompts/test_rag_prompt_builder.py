"""Unit tests for RagPromptBuilder."""
from __future__ import annotations

from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme
from src.infrastructure.prompts import RagPromptBuilder


class TestRagPromptBuilder:
    def _make_request(self, theme: str = "весна", meter: str = "ямб",
                      foot_count: int = 4, scheme: str = "ABAB") -> GenerationRequest:
        return GenerationRequest(
            theme=theme,
            meter=MeterSpec(name=meter, foot_count=foot_count),
            rhyme=RhymeScheme(pattern=scheme),
            structure=PoemStructure(stanza_count=2, lines_per_stanza=4),
        )

    def test_build_returns_string(self):
        prompt = RagPromptBuilder().build(self._make_request(), retrieved=[], examples=[])
        assert isinstance(prompt, str) and len(prompt) > 0

    def test_build_contains_theme(self):
        prompt = RagPromptBuilder().build(self._make_request(theme="тема весна"), [], [])
        assert "тема весна" in prompt

    def test_build_contains_meter_and_scheme(self):
        prompt = RagPromptBuilder().build(
            self._make_request(meter="хорей", scheme="AABB"), [], [],
        )
        assert "хорей" in prompt
        assert "AABB" in prompt

    def test_build_contains_line_count(self):
        prompt = RagPromptBuilder().build(self._make_request(), [], [])
        assert "8 lines" in prompt

    def test_build_plural_stanzas(self):
        prompt = RagPromptBuilder().build(
            GenerationRequest(
                theme="тест", meter=MeterSpec("ямб", 4), rhyme=RhymeScheme("ABAB"),
                structure=PoemStructure(stanza_count=3, lines_per_stanza=4),
            ),
            [], [],
        )
        assert "3 stanzas" in prompt
