"""Contract coverage for `MockLLMProvider`."""
from __future__ import annotations

from src.domain.ports import ILLMProvider
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder
from tests.contracts.llm_provider_contract import ILLMProviderContract


class TestMockLLMProviderContract(ILLMProviderContract):
    def _make_provider(self) -> ILLMProvider:
        return MockLLMProvider(
            regeneration_prompt_builder=NumberedLinesRegenerationPromptBuilder(),
        )
