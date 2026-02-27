from __future__ import annotations

import pytest

from src.generation.llm import LLMClient, LLMResult, MockLLMClient


class TestLLMClientIsABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            LLMClient()


class TestMockLLMClient:
    def test_generate_returns_llm_result(self, mock_llm: MockLLMClient):
        result = mock_llm.generate("будь-який промпт")
        assert isinstance(result, LLMResult)
        assert isinstance(result.text, str)
        assert len(result.text) > 0

    def test_generate_increments_counter(self, mock_llm: MockLLMClient):
        assert mock_llm.generate_calls == 0
        mock_llm.generate("prompt 1")
        assert mock_llm.generate_calls == 1
        mock_llm.generate("prompt 2")
        assert mock_llm.generate_calls == 2

    def test_regenerate_lines_returns_llm_result(self, mock_llm: MockLLMClient):
        result = mock_llm.regenerate_lines("рядок один\nрядок два\n", ["Line 1: violation"])
        assert isinstance(result, LLMResult)
        assert isinstance(result.text, str)

    def test_regenerate_increments_counter(self, mock_llm: MockLLMClient):
        assert mock_llm.regenerate_calls == 0
        mock_llm.regenerate_lines("рядок\n", ["Line 1: meter violation"])
        assert mock_llm.regenerate_calls == 1

    def test_regenerate_modifies_violation_lines(self, mock_llm: MockLLMClient):
        original = "слово один два\nрядок два три\n"
        result = mock_llm.regenerate_lines(original, ["Line 1: meter violation. Rewrite."])
        lines = [ln.strip() for ln in result.text.splitlines() if ln.strip()]
        assert lines[0] != "слово один два"
        assert lines[1] == "рядок два три"

    def test_regenerate_does_not_modify_valid_lines(self, mock_llm: MockLLMClient):
        original = "слово один два\nрядок два три\n"
        result = mock_llm.regenerate_lines(original, ["Line 2: rhyme mismatch."])
        lines = [ln.strip() for ln in result.text.splitlines() if ln.strip()]
        assert lines[0] == "слово один два"

    def test_custom_poem_text(self):
        custom = "мій власний вірш\nдругий рядок\n"
        llm = MockLLMClient(poem_text=custom)
        result = llm.generate("prompt")
        assert result.text == custom
