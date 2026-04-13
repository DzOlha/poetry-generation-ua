"""Unit tests for DetectRunner."""
from __future__ import annotations

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.ports.detection import IDetectionService
from src.infrastructure.logging import CollectingLogger
from src.runners.detect_runner import DetectRunner, DetectRunnerConfig


class _FakeDetectionService(IDetectionService):
    def __init__(self, result: DetectionResult) -> None:
        self._result = result

    def detect(self, poem_text: str, sample_lines: int | None = None) -> DetectionResult:
        return self._result


class TestDetectRunner:
    def test_successful_detection(self) -> None:
        result = DetectionResult(
            meter=MeterDetection(meter="ямб", foot_count=4, accuracy=0.95),
            rhyme=RhymeDetection(scheme="ABAB", accuracy=0.9),
        )
        logger = CollectingLogger()
        runner = DetectRunner(
            config=DetectRunnerConfig(poem_text="some poem"),
            logger=logger,
            detection_service=_FakeDetectionService(result),
        )
        assert runner.run() == 0

    def test_no_detection(self) -> None:
        result = DetectionResult(meter=None, rhyme=None)
        logger = CollectingLogger()
        runner = DetectRunner(
            config=DetectRunnerConfig(poem_text="some poem"),
            logger=logger,
            detection_service=_FakeDetectionService(result),
        )
        assert runner.run() == 0
