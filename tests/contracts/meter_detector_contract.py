"""Behavioural contract for IMeterDetector implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ports.detection import IMeterDetector


class IMeterDetectorContract(ABC):
    """Shared behavioural expectations for any IMeterDetector implementation."""

    @abstractmethod
    def _make_detector(self) -> IMeterDetector: ...

    def test_detect_returns_none_or_meter_detection(self) -> None:
        detector = self._make_detector()
        result = detector.detect("some text that is not a poem")
        # Result must be None or a MeterDetection — no exceptions
        assert result is None or hasattr(result, "meter")

    def test_detect_accuracy_in_range(self) -> None:
        detector = self._make_detector()
        result = detector.detect("some text")
        if result is not None:
            assert 0.0 <= result.accuracy <= 1.0

    def test_detect_foot_count_positive(self) -> None:
        detector = self._make_detector()
        result = detector.detect("some text")
        if result is not None:
            assert result.foot_count >= 1
