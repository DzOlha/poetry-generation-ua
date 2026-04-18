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

        if not isinstance(self.foot_count, int) or isinstance(self.foot_count, bool):
            raise UnsupportedConfigError(
                f"Кількість стоп має бути цілим числом, отримано "
                f"{type(self.foot_count).__name__}."
            )
        if not 1 <= self.foot_count <= 8:
            raise UnsupportedConfigError(
                f"Кількість стоп має бути в діапазоні від 1 до 8, "
                f"отримано {self.foot_count}."
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

    def __post_init__(self) -> None:
        labels = {
            "stanza_count": "Кількість строф",
            "lines_per_stanza": "Кількість рядків у строфі",
        }
        for field_name, label in labels.items():
            val = getattr(self, field_name)
            if not isinstance(val, int) or isinstance(val, bool):
                raise UnsupportedConfigError(
                    f"{label} має бути цілим числом, отримано {type(val).__name__}."
                )
        if self.stanza_count < 1:
            raise UnsupportedConfigError(
                f"Кількість строф має бути не менша за 1, отримано {self.stanza_count}."
            )
        if self.lines_per_stanza < 1:
            raise UnsupportedConfigError(
                f"Кількість рядків у строфі має бути не менша за 1, "
                f"отримано {self.lines_per_stanza}."
            )

    @property
    def total_lines(self) -> int:
        return self.stanza_count * self.lines_per_stanza
