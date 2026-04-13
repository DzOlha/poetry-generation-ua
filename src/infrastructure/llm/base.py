"""Base class for LLM providers — stores the injected regeneration prompt builder.

Concrete LLM providers (Gemini, mock, future OpenAI) inherit from this base
and delegate prompt construction to the injected IRegenerationPromptBuilder
instead of inlining the prompt template.
"""
from __future__ import annotations

from src.domain.ports import ILLMProvider, IRegenerationPromptBuilder


class BaseLLMProvider(ILLMProvider):
    """Holds the shared IRegenerationPromptBuilder dependency."""

    def __init__(self, regeneration_prompt_builder: IRegenerationPromptBuilder) -> None:
        self._regen_prompt_builder = regeneration_prompt_builder

    def _build_regeneration_prompt(self, poem: str, feedback: list[str]) -> str:
        return self._regen_prompt_builder.build(poem, feedback)
