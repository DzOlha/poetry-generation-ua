"""Poem aggregate — the single point that splits raw text into usable lines."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Poem:
    """A parsed poem, exposing line-level behaviour its consumers used to inline.

    Validators, merger, reporter, and stages all used to import
    `split_nonempty_lines` directly. Routing that through a `Poem` aggregate
    means (a) line-splitting logic is centralised, (b) consumers depend only
    on domain objects, and (c) future language-specific parsing can plug in
    via `Poem.from_text` without touching downstream code.
    """

    lines: tuple[str, ...]

    @classmethod
    def from_text(cls, text: str) -> Poem:
        """Parse raw poem text into a Poem, dropping blank lines and trimming whitespace."""
        lines = tuple(ln.strip() for ln in (text or "").splitlines() if ln.strip())
        return cls(lines=lines)

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines

    def as_text(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.lines else "")
