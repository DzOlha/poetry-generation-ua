"""Ukrainian-specific text utilities — shared kernel helpers.

These pure functions are the single source of truth for Ukrainian text
normalization, line splitting, word extraction, and syllable counting.
Infrastructure adapters like `UkrainianTextProcessor` delegate here.
"""
from __future__ import annotations

import re

VOWELS_UA = "аеєиіїоуюя"

__all__ = [
    "VOWELS_UA",
    "normalize_whitespace",
    "split_nonempty_lines",
    "extract_words_ua",
    "count_syllables_ua",
]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_nonempty_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def extract_words_ua(text: str) -> list[str]:
    """Extract Ukrainian words (including apostrophes and hyphens) as lowercase."""
    return re.findall(r"[а-яіїєґʼ\u2019'-]+", text.lower())


def count_syllables_ua(word: str) -> int:
    """Count syllables by counting vowels."""
    return sum(1 for ch in word.lower() if ch in VOWELS_UA)
