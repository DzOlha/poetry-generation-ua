"""Gemini LLM provider — Google Gemini API adapter."""
from __future__ import annotations

from src.domain.errors import LLMError
from src.domain.ports import IRegenerationPromptBuilder
from src.infrastructure.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Implements ILLMProvider using the Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        regeneration_prompt_builder: IRegenerationPromptBuilder,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.9,
        max_output_tokens: int = 4096,
    ) -> None:
        super().__init__(regeneration_prompt_builder=regeneration_prompt_builder)
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise LLMError(
                "google-genai SDK is not installed. Install it or use a different LLM provider."
            ) from exc

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self._model_name = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    def generate(self, prompt: str) -> str:
        system = (
            "You are a Ukrainian poetry generator. "
            "Return only the poem text, no explanations, no markdown."
        )
        return self._call(prompt, system_instruction=system)

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        prompt = self._build_regeneration_prompt(poem, feedback)
        system = "You are refining a Ukrainian poem. Output only the full poem text with all lines."
        return self._call(prompt, system_instruction=system)

    def _call(self, prompt: str, *, system_instruction: str | None = None) -> str:
        try:
            config = self._types.GenerateContentConfig(
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
                system_instruction=system_instruction,
            )
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise LLMError(f"Gemini call failed: {exc}") from exc

        text = response.text
        if not text:
            raise LLMError("Gemini returned an empty response")
        return text.strip() + "\n"
