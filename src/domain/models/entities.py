"""Repository entity objects and query types."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThemeExcerpt:
    """A poem excerpt from the theme corpus."""

    id: str
    text: str
    author: str
    theme: str
    embedding: tuple[float, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class MetricExample:
    """A reference poem that demonstrates a particular meter and rhyme scheme."""

    id: str
    meter: str
    feet: int
    scheme: str
    text: str
    verified: bool = False
    author: str = ""
    note: str = ""


@dataclass(frozen=True)
class MetricQuery:
    """Query object for metric example retrieval."""

    meter: str
    feet: int
    scheme: str
    top_k: int = 3
    verified_only: bool = False


@dataclass(frozen=True)
class RetrievedExcerpt:
    """A theme excerpt paired with its semantic similarity score."""

    excerpt: ThemeExcerpt
    similarity: float


@dataclass(frozen=True)
class LineTokens:
    """Tokenised representation of a single poem line (words + syllable counts)."""

    line: str
    words: tuple[str, ...]
    syllables_per_word: tuple[int, ...]
