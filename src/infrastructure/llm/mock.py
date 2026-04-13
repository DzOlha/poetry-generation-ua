"""Mock LLM provider — deterministic stub for testing and offline development."""
from __future__ import annotations

import re

from src.domain.models import Poem
from src.domain.ports import IRegenerationPromptBuilder
from src.infrastructure.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Returns a hard-coded poem. Used in tests and when no API key is configured.

    Tracks call counts for assertion in tests.
    """

    _DEFAULT_POEM = (
        "Весна прийшла у ліс зелений,\n"
        "Де тінь і світло гомонить.\n"
        "Мов сни, пливуть думки натхненні,\n"
        "І серце в тиші гомонить.\n"
    )

    def __init__(
        self,
        regeneration_prompt_builder: IRegenerationPromptBuilder,
        poem_text: str | None = None,
    ) -> None:
        super().__init__(regeneration_prompt_builder=regeneration_prompt_builder)
        self._poem = poem_text or self._DEFAULT_POEM
        self.generate_calls: int = 0
        self.regenerate_calls: int = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return self._poem

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        """Swap last two words of violating lines (minimal mock behavior)."""
        self.regenerate_calls += 1
        # Exercise the injected builder so tests observe the round-trip.
        _ = self._build_regeneration_prompt(poem, feedback)
        lines = list(Poem.from_text(poem).lines)
        for msg in feedback:
            m = re.search(r"Line\s+(\d+)", msg)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(lines):
                    words = lines[idx].split()
                    if len(words) >= 2:
                        words[-1], words[-2] = words[-2], words[-1]
                    lines[idx] = " ".join(words)
        return "\n".join(lines) + "\n"
