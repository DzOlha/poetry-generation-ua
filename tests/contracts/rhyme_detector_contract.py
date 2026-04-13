"""Behavioural contract for IRhymeDetector implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ports.detection import IRhymeDetector


class IRhymeDetectorContract(ABC):
    """Shared behavioural expectations for any IRhymeDetector implementation."""

    @abstractmethod
    def _make_detector(self) -> IRhymeDetector: ...

    def test_detect_returns_none_or_rhyme_detection(self) -> None:
        detector = self._make_detector()
        result = detector.detect("some text that is not a poem")
        assert result is None or hasattr(result, "scheme")

    def test_detect_accuracy_in_range(self) -> None:
        detector = self._make_detector()
        result = detector.detect("some text")
        if result is not None:
            assert 0.0 <= result.accuracy <= 1.0
