from __future__ import annotations

import pytest

from src.domain.ports import ILLMProvider, IRegenerationPromptBuilder
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder


@pytest.fixture
def regen_prompt_builder() -> IRegenerationPromptBuilder:
    return NumberedLinesRegenerationPromptBuilder()


@pytest.fixture
def mock_llm(regen_prompt_builder) -> MockLLMProvider:
    return MockLLMProvider(regeneration_prompt_builder=regen_prompt_builder)


class TestLLMProviderIsABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ILLMProvider()  # type: ignore[abstract]


class TestMockLLMProvider:
    def test_generate_returns_str(self, mock_llm: MockLLMProvider):
        result = mock_llm.generate("будь-який промпт")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_increments_counter(self, mock_llm: MockLLMProvider):
        assert mock_llm.generate_calls == 0
        mock_llm.generate("prompt 1")
        assert mock_llm.generate_calls == 1
        mock_llm.generate("prompt 2")
        assert mock_llm.generate_calls == 2

    def test_regenerate_lines_returns_str(self, mock_llm: MockLLMProvider):
        result = mock_llm.regenerate_lines("рядок один\nрядок два\n", ["Line 1: violation"])
        assert isinstance(result, str)

    def test_regenerate_increments_counter(self, mock_llm: MockLLMProvider):
        assert mock_llm.regenerate_calls == 0
        mock_llm.regenerate_lines("рядок\n", ["Line 1: meter violation"])
        assert mock_llm.regenerate_calls == 1

    def test_regenerate_modifies_violation_lines(self, mock_llm: MockLLMProvider):
        original = "слово один два\nрядок два три\n"
        result = mock_llm.regenerate_lines(original, ["Line 1: meter violation. Rewrite."])
        lines = [ln.strip() for ln in result.splitlines() if ln.strip()]
        assert lines[0] != "слово один два"
        assert lines[1] == "рядок два три"

    def test_regenerate_does_not_modify_valid_lines(self, mock_llm: MockLLMProvider):
        original = "слово один два\nрядок два три\n"
        result = mock_llm.regenerate_lines(original, ["Line 2: rhyme mismatch."])
        lines = [ln.strip() for ln in result.splitlines() if ln.strip()]
        assert lines[0] == "слово один два"

    def test_custom_poem_text(self, regen_prompt_builder):
        custom = "мій власний вірш\nдругий рядок\n"
        llm = MockLLMProvider(regeneration_prompt_builder=regen_prompt_builder, poem_text=custom)
        result = llm.generate("prompt")
        assert result == custom
