"""Text-processing primitive ports (split per ISP)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import LineTokens


class ILineSplitter(ABC):
    """Splits a block of text into non-empty, stripped lines."""

    @abstractmethod
    def split_lines(self, text: str) -> list[str]: ...


class ITokenizer(ABC):
    """Tokenizes a line into words with per-word syllable counts."""

    @abstractmethod
    def tokenize_line(self, text: str) -> LineTokens: ...

    @abstractmethod
    def extract_words(self, text: str) -> list[str]: ...


class IStringSimilarity(ABC):
    """Computes a normalised [0, 1] similarity between two strings.

    Kept as its own port so the rhyme validator can inject a Levenshtein-based
    scorer while text processors only need to know about tokenisation.
    """

    @abstractmethod
    def similarity(self, a: str, b: str) -> float: ...


class ITextProcessor(ILineSplitter, ITokenizer):
    """Full text-processing facade for callers that need everything.

    Extends the narrow ports above for convenience; consumers are still
    encouraged to depend on the smallest interface they actually need
    (ILineSplitter alone is usually enough).
    """

    @abstractmethod
    def count_syllables(self, word: str) -> int: ...

    @abstractmethod
    def normalize_whitespace(self, text: str) -> str: ...
