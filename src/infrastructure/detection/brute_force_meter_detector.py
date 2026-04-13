"""Brute-force meter detector — tries all meter × foot-count combinations.

Iterates over every canonical Ukrainian meter and a configurable range of
foot counts, validates each against the provided text, and returns the
combination with the highest accuracy (if it exceeds the threshold).
"""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.detection import MeterDetection
from src.domain.models import MeterSpec
from src.domain.ports.detection import IMeterDetector
from src.domain.ports.validation import IMeterValidator
from src.domain.values import MeterName

# Canonical meters to try (excludes English aliases).
_CANONICAL_METERS: tuple[MeterName, ...] = (
    MeterName.IAMB,
    MeterName.TROCHEE,
    MeterName.DACTYL,
    MeterName.AMPHIBRACH,
    MeterName.ANAPEST,
)


class BruteForceMeterDetector(IMeterDetector):
    """Tries every meter × foot-count pair and picks the highest-accuracy match."""

    def __init__(
        self,
        meter_validator: IMeterValidator,
        config: DetectionConfig,
    ) -> None:
        self._validator = meter_validator
        self._min_accuracy = config.meter_min_accuracy
        self._feet_min = config.feet_min
        self._feet_max = config.feet_max

    def detect(self, text: str) -> MeterDetection | None:
        best: MeterDetection | None = None

        for meter in _CANONICAL_METERS:
            for feet in range(self._feet_min, self._feet_max + 1):
                spec = MeterSpec(name=meter.value, foot_count=feet)
                result = self._validator.validate(text, spec)
                if result.accuracy < self._min_accuracy:
                    continue
                if best is None or result.accuracy > best.accuracy:
                    best = MeterDetection(
                        meter=meter.value,
                        foot_count=feet,
                        accuracy=result.accuracy,
                    )

        return best
