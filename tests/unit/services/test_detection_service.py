"""Unit tests for DetectionService."""
from __future__ import annotations

from src.domain.detection import MeterDetection, RhymeDetection
from src.domain.ports.detection import IMeterDetector, IRhymeDetector, IStanzaSampler
from src.infrastructure.logging import NullLogger
from src.services.detection_service import DetectionService


class _FakeSampler(IStanzaSampler):
    def __init__(self, result: str | None = "line1\nline2\nline3\nline4") -> None:
        self._result = result
        self.last_line_count: int | None = None

    def sample(self, poem_text: str, line_count: int) -> str | None:
        self.last_line_count = line_count
        return self._result


class _FakeMeterDetector(IMeterDetector):
    def __init__(self, result: MeterDetection | None = None) -> None:
        self._result = result

    def detect(self, text: str) -> MeterDetection | None:
        return self._result


class _FakeRhymeDetector(IRhymeDetector):
    def __init__(self, result: RhymeDetection | None = None) -> None:
        self._result = result

    def detect(self, text: str) -> RhymeDetection | None:
        return self._result


def _make_service(
    sampler: IStanzaSampler | None = None,
    meter: IMeterDetector | None = None,
    rhyme: IRhymeDetector | None = None,
) -> DetectionService:
    return DetectionService(
        sampler=sampler or _FakeSampler(),
        meter_detector=meter or _FakeMeterDetector(),
        rhyme_detector=rhyme or _FakeRhymeDetector(),
        default_sample_lines=4,
        logger=NullLogger(),
    )


class TestDetectionService:
    def test_returns_both_detected(self) -> None:
        md = MeterDetection(meter="ямб", foot_count=4, accuracy=0.95)
        rd = RhymeDetection(scheme="ABAB", accuracy=0.9)
        svc = _make_service(
            meter=_FakeMeterDetector(md),
            rhyme=_FakeRhymeDetector(rd),
        )
        result = svc.detect("some poem text")
        assert result.is_detected
        assert result.meter == md
        assert result.rhyme == rd

    def test_returns_none_when_poem_too_short(self) -> None:
        svc = _make_service(sampler=_FakeSampler(result=None))
        result = svc.detect("short")
        assert result.meter is None
        assert result.rhyme is None

    def test_passes_custom_sample_lines(self) -> None:
        sampler = _FakeSampler()
        svc = _make_service(sampler=sampler)
        svc.detect("some text", sample_lines=4)
        assert sampler.last_line_count == 4

    def test_uses_default_sample_lines(self) -> None:
        sampler = _FakeSampler()
        svc = _make_service(sampler=sampler)
        svc.detect("some text")
        assert sampler.last_line_count == 4

    def test_returns_partial_when_only_meter(self) -> None:
        md = MeterDetection(meter="ямб", foot_count=4, accuracy=0.95)
        svc = _make_service(meter=_FakeMeterDetector(md))
        result = svc.detect("text")
        assert result.meter is not None
        assert result.rhyme is None
        assert result.is_detected is False
