"""Unit tests for BruteForceMeterDetector."""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.models import MeterResult, MeterSpec
from src.domain.ports.validation import IMeterValidator
from src.infrastructure.detection import BruteForceMeterDetector


class _FixedAccuracyValidator(IMeterValidator):
    """Returns a fixed accuracy for one specific meter, 0.0 for all others."""

    def __init__(self, target_meter: str, target_feet: int, accuracy: float) -> None:
        self._target_meter = target_meter
        self._target_feet = target_feet
        self._accuracy = accuracy

    def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult:
        if meter.name == self._target_meter and meter.foot_count == self._target_feet:
            return MeterResult(ok=True, accuracy=self._accuracy)
        return MeterResult(ok=False, accuracy=0.0)


class TestBruteForceMeterDetector:
    def test_detects_iamb_4(self) -> None:
        validator = _FixedAccuracyValidator("ямб", 4, 0.95)
        detector = BruteForceMeterDetector(
            meter_validator=validator,
            config=DetectionConfig(meter_min_accuracy=0.85),
        )
        result = detector.detect("dummy text")
        assert result is not None
        assert result.meter == "ямб"
        assert result.foot_count == 4
        assert result.accuracy == 0.95

    def test_returns_none_below_threshold(self) -> None:
        validator = _FixedAccuracyValidator("ямб", 4, 0.5)
        detector = BruteForceMeterDetector(
            meter_validator=validator,
            config=DetectionConfig(meter_min_accuracy=0.85),
        )
        result = detector.detect("dummy text")
        assert result is None

    def test_picks_highest_accuracy(self) -> None:
        """When multiple combinations exceed threshold, pick the best."""
        class _MultiValidator(IMeterValidator):
            def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult:
                if meter.name == "ямб" and meter.foot_count == 4:
                    return MeterResult(ok=True, accuracy=0.90)
                if meter.name == "хорей" and meter.foot_count == 4:
                    return MeterResult(ok=True, accuracy=0.95)
                return MeterResult(ok=False, accuracy=0.0)

        detector = BruteForceMeterDetector(
            meter_validator=_MultiValidator(),
            config=DetectionConfig(meter_min_accuracy=0.85),
        )
        result = detector.detect("dummy text")
        assert result is not None
        assert result.meter == "хорей"
        assert result.accuracy == 0.95

    def test_respects_feet_range(self) -> None:
        """Should only try feet in configured range."""
        calls: list[int] = []

        class _RecordingValidator(IMeterValidator):
            def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult:
                calls.append(meter.foot_count)
                return MeterResult(ok=False, accuracy=0.0)

        detector = BruteForceMeterDetector(
            meter_validator=_RecordingValidator(),
            config=DetectionConfig(feet_min=3, feet_max=5),
        )
        detector.detect("dummy")
        unique_feet = set(calls)
        assert unique_feet == {3, 4, 5}
