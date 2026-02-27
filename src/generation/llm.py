from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.utils.text import split_nonempty_lines


def merge_regenerated_poem(original: str, regenerated: str, feedback: list[str]) -> str:
    """Ensure the regenerated poem has the same number of lines as the original.

    If the LLM returned only the fixed lines (truncated), we replace only the
    lines referenced in feedback and keep all other original lines intact.
    This guarantees that meter/rhyme metrics are always computed on the full poem.
    """
    orig_lines = split_nonempty_lines(original)
    regen_lines = split_nonempty_lines(regenerated)

    if len(regen_lines) == len(orig_lines):
        return regenerated

    changed: set[int] = set()
    for msg in feedback:
        for m in re.finditer(r"[Ll]ine[s]?\s+(\d+)(?:\s+and\s+(\d+))?", msg):
            changed.add(int(m.group(1)) - 1)
            if m.group(2):
                changed.add(int(m.group(2)) - 1)

    if not changed or len(regen_lines) < len(changed):
        return regenerated

    merged = list(orig_lines)
    for new_idx, orig_idx in enumerate(sorted(changed)):
        if new_idx < len(regen_lines) and orig_idx < len(merged):
            merged[orig_idx] = regen_lines[new_idx]

    return "\n".join(merged) + "\n"


@dataclass(frozen=True)
class LLMResult:
    text: str


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> LLMResult:
        ...

    @abstractmethod
    def regenerate_lines(self, poem_text: str, feedback: list[str]) -> LLMResult:
        ...


class GeminiLLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.9,
        max_output_tokens: int = 4096,
    ) -> None:
        from google import genai
        from google.genai import types

        self._client = genai.Client(api_key=api_key)
        self._types = types
        self._model_name = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    def _generate_text(self, prompt: str, system_instruction: str | None = None) -> str:
        config = self._types.GenerateContentConfig(
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
        )
        if system_instruction:
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
        text = response.text
        if not text:
            raise RuntimeError("Gemini returned empty response")
        return text.strip() + "\n"

    def generate(self, prompt: str) -> LLMResult:
        system = (
            "You are a Ukrainian poetry generator. "
            "Return only the poem text, no explanations, no markdown."
        )
        return LLMResult(text=self._generate_text(prompt, system_instruction=system))

    def regenerate_lines(self, poem_text: str, feedback: list[str]) -> LLMResult:
        fb = "\n".join(feedback)
        lines = poem_text.strip().splitlines()
        numbered = "\n".join(f"{i + 1}: {ln}" for i, ln in enumerate(lines))
        prompt = (
            "You are given a Ukrainian poem with line numbers and a list of violations.\n"
            "Fix ONLY the lines mentioned in the feedback. Copy all other lines exactly unchanged.\n"
            "Return the COMPLETE poem — every line, in the correct order — with no line numbers, "
            "no commentary, no markdown.\n\n"
            "POEM (with line numbers for reference):\n"
            f"{numbered}\n\n"
            "VIOLATIONS TO FIX:\n"
            f"{fb}\n"
        )
        system = "You are refining a Ukrainian poem. Output only the full poem text with all lines."
        return LLMResult(text=self._generate_text(prompt, system_instruction=system))


class MockLLMClient(LLMClient):
    def __init__(self, poem_text: str | None = None) -> None:
        self._poem = poem_text or (
            "Весна прийшла у ліс зелений,\n"
            "Де тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\n"
            "І серце в тиші гомонить.\n"
        )
        self.generate_calls: int = 0
        self.regenerate_calls: int = 0

    def generate(self, prompt: str) -> LLMResult:
        self.generate_calls += 1
        return LLMResult(text=self._poem)

    def regenerate_lines(self, poem_text: str, feedback: list[str]) -> LLMResult:
        self.regenerate_calls += 1
        lines = split_nonempty_lines(poem_text)
        violation_indices: set[int] = set()
        for msg in feedback:
            m = re.search(r"Line\s+(\d+)", msg)
            if m:
                violation_indices.add(int(m.group(1)) - 1)
        for idx in violation_indices:
            if 0 <= idx < len(lines):
                words = lines[idx].split()
                if len(words) >= 2:
                    words[-1], words[-2] = words[-2], words[-1]
                lines[idx] = " ".join(words)
        return LLMResult(text="\n".join(lines) + "\n")


def llm_from_env() -> LLMClient | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    model = os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
    temperature = float(os.getenv("GEMINI_TEMPERATURE") or "0.9")
    max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS") or "4096")
    return GeminiLLMClient(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
