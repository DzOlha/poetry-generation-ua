"""Port for corpus parsing — extracting poems from raw text sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedPoem:
    """A single poem extracted from a text source."""

    title: str | None
    text: str


class ICorpusParser(ABC):
    """Parses raw text into structured poem records."""

    @abstractmethod
    def parse_numbered_poems(self, raw_text: str) -> list[ParsedPoem]:
        """Parse numbered poems from text in ``N. Title\\nBody`` format."""

    @abstractmethod
    def normalize_poem_text(self, text: str) -> str:
        """Normalize whitespace, line endings, and collapse multiple blank lines."""

    @abstractmethod
    def looks_like_poem(
        self,
        clean_text: str,
        min_lines: int = 4,
        min_chars: int = 60,
        max_chars: int = 10_000,
    ) -> bool:
        """Heuristic check whether a text block looks like a poem."""

    @abstractmethod
    def author_from_path(self, path: Path, data_dir: Path) -> str | None:
        """Extract author name from the first path component relative to data_dir."""
