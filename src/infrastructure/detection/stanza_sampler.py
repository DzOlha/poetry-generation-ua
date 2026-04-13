"""IStanzaSampler implementation — extracts leading non-empty lines.

The ``line_count`` parameter makes this extensible:
  - 4 lines  → standard quatrain detection (ABAB, AABB, ABBA)
  - 2 lines  → couplet detection
  - 3 lines  → tercet detection
  - 14 lines → sonnet compound-scheme detection (future)
"""
from __future__ import annotations

from src.domain.ports.detection import IStanzaSampler
from src.domain.ports.text import ILineSplitter


class FirstLinesStanzaSampler(IStanzaSampler):
    """Samples the first ``line_count`` non-empty lines from poem text."""

    def __init__(self, line_splitter: ILineSplitter) -> None:
        self._splitter = line_splitter

    def sample(self, poem_text: str, line_count: int) -> str | None:
        lines = self._splitter.split_lines(poem_text)
        if len(lines) < line_count:
            return None
        return "\n".join(lines[:line_count])
