"""Unit tests for detection domain models."""
from __future__ import annotations

import pytest

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.errors import UnsupportedConfigError


class TestMeterDetection:
    def test_frozen(self) -> None:
        d = MeterDetection(meter="ямб", foot_count=4, accuracy=0.9)
        with pytest.raises(AttributeError):
            d.meter = "хорей"  # type: ignore[misc]

    def test_meter_enum(self) -> None:
        d = MeterDetection(meter="ямб", foot_count=4, accuracy=0.9)
        assert d.meter_enum.value == "ямб"

    def test_invalid_meter_enum(self) -> None:
        d = MeterDetection(meter="unknown", foot_count=4, accuracy=0.9)
        with pytest.raises(UnsupportedConfigError):
            _ = d.meter_enum


class TestRhymeDetection:
    def test_frozen(self) -> None:
        d = RhymeDetection(scheme="ABAB", accuracy=0.8)
        with pytest.raises(AttributeError):
            d.scheme = "AABB"  # type: ignore[misc]

    def test_scheme_enum(self) -> None:
        d = RhymeDetection(scheme="ABAB", accuracy=0.8)
        assert d.scheme_enum.value == "ABAB"


class TestDetectionResult:
    def test_is_detected_both_present(self) -> None:
        r = DetectionResult(
            meter=MeterDetection(meter="ямб", foot_count=4, accuracy=0.9),
            rhyme=RhymeDetection(scheme="ABAB", accuracy=0.8),
        )
        assert r.is_detected is True

    def test_is_detected_meter_missing(self) -> None:
        r = DetectionResult(
            meter=None,
            rhyme=RhymeDetection(scheme="ABAB", accuracy=0.8),
        )
        assert r.is_detected is False

    def test_is_detected_both_missing(self) -> None:
        r = DetectionResult(meter=None, rhyme=None)
        assert r.is_detected is False
