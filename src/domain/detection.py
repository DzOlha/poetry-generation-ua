"""Detection result models — frozen value objects for meter/rhyme classification.

Used by the detection service and runners to communicate results of
brute-force meter/rhyme identification from raw poem text.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.values import MeterName, RhymePattern


@dataclass(frozen=True)
class MeterDetection:
    """Best-match meter identified for a text sample."""

    meter: str
    foot_count: int
    accuracy: float

    @property
    def meter_enum(self) -> MeterName:
        return MeterName.parse(self.meter)


@dataclass(frozen=True)
class RhymeDetection:
    """Best-match rhyme scheme identified for a text sample."""

    scheme: str
    accuracy: float

    @property
    def scheme_enum(self) -> RhymePattern:
        return RhymePattern.parse(self.scheme)


@dataclass(frozen=True)
class DetectionResult:
    """Combined meter + rhyme detection for a poem sample."""

    meter: MeterDetection | None
    rhyme: RhymeDetection | None

    @property
    def is_detected(self) -> bool:
        """True if both meter and rhyme were detected above thresholds."""
        return self.meter is not None and self.rhyme is not None
