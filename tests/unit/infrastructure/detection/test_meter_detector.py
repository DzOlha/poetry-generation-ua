"""Unit tests for BruteForceMeterDetector."""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.models import LineMeterResult, MeterResult, MeterSpec
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

    def test_tie_break_prefers_fewer_errors(self) -> None:
        """When two meters tie on accuracy, fewer total error positions wins.

        Reproduces the «шибочках/кутиках» case: a 6-syllable dactylic line
        validates as both iamb 2-foot (passing with 2 errors per line via
        the `allowed_mismatches=2` budget) and dactyl 2-foot (exact length,
        0 errors). Both pass at accuracy=1.0, but dactyl fits cleanly.
        Without this tie-break the iteration order silently picked iamb.
        """
        def _line(error_count: int) -> LineMeterResult:
            return LineMeterResult(
                ok=True,
                expected_stresses=(),
                actual_stresses=(),
                error_positions=tuple(range(1, error_count + 1)),
                total_syllables=6,
            )

        class _TieValidator(IMeterValidator):
            def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult:
                if meter.name == "ямб" and meter.foot_count == 2:
                    return MeterResult(
                        ok=True, accuracy=1.0,
                        line_results=tuple(_line(2) for _ in range(4)),
                    )
                if meter.name == "дактиль" and meter.foot_count == 2:
                    return MeterResult(
                        ok=True, accuracy=1.0,
                        line_results=tuple(_line(0) for _ in range(4)),
                    )
                return MeterResult(ok=False, accuracy=0.0)

        detector = BruteForceMeterDetector(
            meter_validator=_TieValidator(),
            config=DetectionConfig(meter_min_accuracy=0.85),
        )
        result = detector.detect("dummy")
        assert result is not None
        assert result.meter == "дактиль"
        assert result.foot_count == 2

    def test_respects_feet_range(self) -> None:
        """Should only try feet in configured range, and try every value in it."""
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

        # No feet outside [3, 5] tried — protects against off-by-one in
        # the range loop or a default that ignores the config.
        assert all(3 <= ft <= 5 for ft in calls), f"out-of-range feet: {calls}"
        # Every value in the inclusive range is exercised — protects
        # against a `range(min, max)` (exclusive) regression that would
        # silently drop feet=5 from detection.
        assert set(calls) == {3, 4, 5}
        # Each foot count is tried for every canonical meter (5).
        # If someone reduces _CANONICAL_METERS without updating callers,
        # this fails loudly.
        from src.infrastructure.detection.brute_force_meter_detector import (
            _CANONICAL_METERS,
        )
        assert calls.count(3) == len(_CANONICAL_METERS)
        assert calls.count(4) == len(_CANONICAL_METERS)
        assert calls.count(5) == len(_CANONICAL_METERS)
