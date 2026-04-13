"""Specification value objects — MeterSpec, RhymeScheme, PoemStructure.

These validate eagerly via enum parsing so unknown values raise at the
system boundary rather than deep in validators.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors import UnsupportedConfigError
from src.domain.values import MeterName, RhymePattern


@dataclass(frozen=True)
class MeterSpec:
    """Metrical specification: canonical meter name + foot count per line.

    Construction fails fast on unknown meter names (via `MeterName.parse`).
    """

    name: str
    foot_count: int

    def __post_init__(self) -> None:
        parsed = MeterName.parse(self.name)
        object.__setattr__(self, "name", parsed.canonical().value)

        if self.foot_count < 0:
            raise UnsupportedConfigError(
                f"foot_count must be >= 0, got {self.foot_count}"
            )


@dataclass(frozen=True)
class RhymeScheme:
    """Rhyme pattern value object (ABAB, AABB, ABBA, AAAA).

    Parses eagerly via `RhymePattern.parse` so unknown patterns raise at the
    system boundary rather than deep inside the rhyme extractor.
    """

    pattern: str

    def __post_init__(self) -> None:
        parsed = RhymePattern.parse(self.pattern)
        object.__setattr__(self, "pattern", parsed.value)

    @property
    def as_enum(self) -> RhymePattern:
        return RhymePattern.parse(self.pattern)


@dataclass(frozen=True)
class PoemStructure:
    """Stanzaic shape of a poem."""

    stanza_count: int
    lines_per_stanza: int

    @property
    def total_lines(self) -> int:
        return self.stanza_count * self.lines_per_stanza
