"""Ukrainian syllable counter adapter — wraps the shared helper behind ISyllableCounter."""
from __future__ import annotations

from src.domain.ports import ISyllableCounter
from src.shared.text_utils_ua import count_syllables_ua


class UkrainianSyllableCounter(ISyllableCounter):
    """ISyllableCounter for Ukrainian (vowel-counting heuristic)."""

    def count(self, word: str) -> int:
        return count_syllables_ua(word)
