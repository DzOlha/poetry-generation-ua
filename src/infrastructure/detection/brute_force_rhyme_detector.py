"""Brute-force rhyme detector — tries all supported rhyme schemes.

Iterates over every canonical rhyme pattern, validates each against the
provided text, and returns the one with the highest accuracy (if it
exceeds the threshold).
"""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.detection import RhymeDetection
from src.domain.models import RhymeScheme
from src.domain.ports.detection import IRhymeDetector
from src.domain.ports.validation import IRhymeValidator
from src.domain.values import RhymePattern

# Patterns to try (AAAA excluded: monorhyme is rare and inflates false positives).
_CANDIDATE_PATTERNS: tuple[RhymePattern, ...] = (
    RhymePattern.ABAB,
    RhymePattern.AABB,
    RhymePattern.ABBA,
)


class BruteForceRhymeDetector(IRhymeDetector):
    """Tries every rhyme scheme and picks the highest-accuracy match."""

    def __init__(
        self,
        rhyme_validator: IRhymeValidator,
        config: DetectionConfig,
    ) -> None:
        self._validator = rhyme_validator
        self._min_accuracy = config.rhyme_min_accuracy

    def detect(self, text: str) -> RhymeDetection | None:
        best: RhymeDetection | None = None

        for pattern in _CANDIDATE_PATTERNS:
            scheme = RhymeScheme(pattern=pattern.value)
            result = self._validator.validate(text, scheme)
            if result.accuracy < self._min_accuracy:
                continue
            if best is None or result.accuracy > best.accuracy:
                best = RhymeDetection(
                    scheme=pattern.value,
                    accuracy=result.accuracy,
                )

        return best
