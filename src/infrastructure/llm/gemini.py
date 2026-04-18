"""Gemini LLM provider — Google Gemini API adapter."""
from __future__ import annotations

from typing import Any

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
        disable_thinking: bool = True,
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
        self._disable_thinking = disable_thinking

    _FORBIDDEN_OUTPUT_RULES = (
        "STRICT OUTPUT RULES — violating ANY of these is a failure:\n"
        "1. Write each word in normal Ukrainian orthography (lowercase + standard "
        "capitalization only at the start of a line or for proper nouns).\n"
        "2. NEVER write words in ALL CAPS to mark stress "
        "(forbidden: 'І-ДУТЬ', 'СЛАВ-ний', 'БІЙ', 'РІД-ну ЗЕМ-лю').\n"
        "3. NEVER split words into syllables with hyphens "
        "(forbidden: 'За-гу-бив-ся', 'і-ду-ть', 'ле-тить').\n"
        "4. NEVER number syllables with parentheses "
        "(forbidden: 'Слу(1) жи(2) ли(3)', 'А (1) ни (2) ні (3)').\n"
        "5. NEVER output scansion marks "
        "(forbidden: 'u u -', '( - )', '(U)', '-> ', '/ - /').\n"
        "6. NEVER output bare number sequences like '1 2 3 4 5 6 7 8'.\n"
        "7. NEVER include English words, drafts, alternative variants, "
        "markdown, bullets, line numbers, or commentary of any kind.\n"
        "8. No preamble, no epilogue — first token must be the first word "
        "of the first poem line; last token must be the final word/punctuation "
        "of the last poem line.\n"
    )

    _ENVELOPE_RULE = (
        "You may reason freely BEFORE emitting <POEM>. Emit the literal tag "
        "<POEM> on its own, then the final Ukrainian poem (one line per verse "
        "line, normal orthography), then </POEM> immediately after the last "
        "poem line. Write NOTHING after </POEM>. All format rules below apply "
        "to the content BETWEEN the tags.\n\n"
    )

    def generate(self, prompt: str) -> str:
        system = (
            "You are a Ukrainian poetry generator. "
            "Your final poem must be wrapped between <POEM> and </POEM> tags.\n\n"
            + self._ENVELOPE_RULE
            + self._FORBIDDEN_OUTPUT_RULES
        )
        return self._call(prompt, system_instruction=system)

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        prompt = self._build_regeneration_prompt(poem, feedback)
        system = (
            "You are refining a Ukrainian poem. Your final corrected poem must "
            "be wrapped between <POEM> and </POEM> tags.\n"
            "The feedback you receive may show syllable stress diagrams and "
            "numbered syllables to explain violations — those are EXPLANATIONS, "
            "NOT the format you should output. Your output must be plain poem lines "
            "in normal Ukrainian orthography.\n\n"
            + self._ENVELOPE_RULE
            + self._FORBIDDEN_OUTPUT_RULES
        )
        return self._call(prompt, system_instruction=system)

    def _call(self, prompt: str, *, system_instruction: str | None = None) -> str:
        try:
            config = self._types.GenerateContentConfig(
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
                system_instruction=system_instruction,
                thinking_config=self._build_thinking_config(),
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

    def _build_thinking_config(self) -> Any:
        """Return a ``ThinkingConfig`` that suppresses visible reasoning, or None.

        Reasoning-first Gemini variants (2.5 Pro / 3.x Pro) emit extensive
        chain-of-thought by default and truncate before reaching the poem
        envelope once ``max_output_tokens`` is hit. Setting
        ``thinking_budget=0`` + ``include_thoughts=False`` redirects the
        whole token budget to the actual answer. Silently skipped when the
        installed SDK version does not ship ``ThinkingConfig`` — older
        models ignore the field anyway.
        """
        if not self._disable_thinking:
            return None
        thinking_cfg_cls = getattr(self._types, "ThinkingConfig", None)
        if thinking_cfg_cls is None:
            return None
        try:
            return thinking_cfg_cls(thinking_budget=0, include_thoughts=False)
        except TypeError:
            # SDK version exposes the class but with different kwargs —
            # keep running without the optimisation rather than crash.
            return None
