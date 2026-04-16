"""Unit tests for DetectionService — full-text detection (not sampled).

Verifies that the detection service passes the complete poem text to
detectors instead of a sampled subset, while still using the sampler
for minimum line count validation.
"""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.detection import MeterDetection, RhymeDetection
from src.domain.ports.detection import IMeterDetector, IRhymeDetector, IStanzaSampler
from src.infrastructure.logging import NullLogger
from src.services.detection_service import DetectionService


class _SpySampler(IStanzaSampler):
    """Records calls and returns a configurable result."""

    def __init__(self, result: str | None = "ok") -> None:
        self._result = result
        self.calls: list[tuple[str, int]] = []

    def sample(self, poem_text: str, line_count: int) -> str | None:
        self.calls.append((poem_text, line_count))
        return self._result


class _SpyMeterDetector(IMeterDetector):
    """Records the text it receives."""

    def __init__(self) -> None:
        self.received_text: str | None = None

    def detect(self, text: str) -> MeterDetection | None:
        self.received_text = text
        return MeterDetection(meter="ямб", foot_count=4, accuracy=0.9)


class _SpyRhymeDetector(IRhymeDetector):
    """Records the text it receives."""

    def __init__(self) -> None:
        self.received_text: str | None = None

    def detect(self, text: str) -> RhymeDetection | None:
        self.received_text = text
        return RhymeDetection(scheme="ABAB", accuracy=0.8)


class TestDetectionReceivesFullText:
    def test_meter_detector_gets_full_poem(self) -> None:
        full_poem = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8"
        meter_spy = _SpyMeterDetector()
        svc = DetectionService(
            sampler=_SpySampler(),
            meter_detector=meter_spy,
            rhyme_detector=_SpyRhymeDetector(),
            config=DetectionConfig(),
            logger=NullLogger(),
        )
        svc.detect(full_poem)
        assert meter_spy.received_text == full_poem

    def test_rhyme_detector_gets_full_poem(self) -> None:
        full_poem = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\nLine 7\nLine 8"
        rhyme_spy = _SpyRhymeDetector()
        svc = DetectionService(
            sampler=_SpySampler(),
            meter_detector=_SpyMeterDetector(),
            rhyme_detector=rhyme_spy,
            config=DetectionConfig(),
            logger=NullLogger(),
        )
        svc.detect(full_poem)
        assert rhyme_spy.received_text == full_poem

    def test_sampler_used_only_for_minimum_check(self) -> None:
        sampler = _SpySampler(result=None)
        svc = DetectionService(
            sampler=sampler,
            meter_detector=_SpyMeterDetector(),
            rhyme_detector=_SpyRhymeDetector(),
            config=DetectionConfig(),
            logger=NullLogger(),
        )
        result = svc.detect("short")
        assert result.meter is None
        assert result.rhyme is None
        assert len(sampler.calls) == 1
