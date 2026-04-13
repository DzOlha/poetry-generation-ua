"""ITextProcessor adapter for Ukrainian text.

The adapter implements the narrow text-processing ports (`ILineSplitter`,
`ITokenizer`) plus the full `ITextProcessor` facade.
Consumers are encouraged to depend on the smallest port they actually need.
`IStringSimilarity` is implemented separately by `LevenshteinSimilarity`.
"""
from __future__ import annotations

from src.domain.models import LineTokens
from src.domain.ports import (
    ILineSplitter,
    ITextProcessor,
    ITokenizer,
)
from src.shared.text_utils_ua import (
    count_syllables_ua,
    extract_words_ua,
    split_nonempty_lines,
)
from src.shared.text_utils_ua import (
    normalize_whitespace as _normalize_whitespace,
)


class UkrainianTextProcessor(ITextProcessor, ILineSplitter, ITokenizer):
    """ITextProcessor implementation for Ukrainian poetry text."""

    # --- ILineSplitter ---------------------------------------------------

    def split_lines(self, text: str) -> list[str]:
        return split_nonempty_lines(text)

    # --- ITokenizer ------------------------------------------------------

    def tokenize_line(self, text: str) -> LineTokens:
        words = extract_words_ua(text)
        syllables = tuple(count_syllables_ua(w) for w in words)
        return LineTokens(line=text, words=tuple(words), syllables_per_word=syllables)

    def extract_words(self, text: str) -> list[str]:
        return extract_words_ua(text)

    # --- ITextProcessor convenience --------------------------------------

    def count_syllables(self, word: str) -> int:
        return count_syllables_ua(word)

    def normalize_whitespace(self, text: str) -> str:
        return _normalize_whitespace(text)
