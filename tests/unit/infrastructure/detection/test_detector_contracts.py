"""Contract tests: BruteForceMeterDetector and BruteForceRhymeDetector."""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.ports.detection import IMeterDetector, IRhymeDetector
from src.infrastructure.detection import BruteForceMeterDetector, BruteForceRhymeDetector
from tests.contracts.meter_detector_contract import IMeterDetectorContract
from tests.contracts.rhyme_detector_contract import IRhymeDetectorContract


class TestBruteForceMeterDetectorContract(IMeterDetectorContract):
    def _make_detector(self) -> IMeterDetector:
        from tests.unit.infrastructure.detection.test_meter_detector import (
            _FixedAccuracyValidator,
        )
        return BruteForceMeterDetector(
            meter_validator=_FixedAccuracyValidator("ямб", 4, 0.95),
            config=DetectionConfig(),
        )


class TestBruteForceRhymeDetectorContract(IRhymeDetectorContract):
    def _make_detector(self) -> IRhymeDetector:
        from tests.unit.infrastructure.detection.test_rhyme_detector import (
            _FixedAccuracyValidator,
        )
        return BruteForceRhymeDetector(
            rhyme_validator=_FixedAccuracyValidator("ABAB", 0.9),
            config=DetectionConfig(),
        )
