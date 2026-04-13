"""Detection service — facade for meter/rhyme auto-detection.

Combines stanza sampling with brute-force detection to classify a poem's
meter and rhyme scheme from its raw text.
"""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.detection import DetectionResult
from src.domain.ports.detection import (
    IDetectionService,
    IMeterDetector,
    IRhymeDetector,
    IStanzaSampler,
)
from src.domain.ports.logging import ILogger


class DetectionService(IDetectionService):
    """Orchestrates sampling → meter detection → rhyme detection."""

    def __init__(
        self,
        sampler: IStanzaSampler,
        meter_detector: IMeterDetector,
        rhyme_detector: IRhymeDetector,
        config: DetectionConfig,
        logger: ILogger,
    ) -> None:
        self._sampler = sampler
        self._meter = meter_detector
        self._rhyme = rhyme_detector
        self._default_sample_lines = config.sample_lines
        self._logger = logger

    def detect(self, poem_text: str, sample_lines: int | None = None) -> DetectionResult:
        n_lines = sample_lines or self._default_sample_lines
        sample = self._sampler.sample(poem_text, n_lines)
        if sample is None:
            self._logger.info(
                "Poem too short for detection",
                required_lines=n_lines,
            )
            return DetectionResult(meter=None, rhyme=None)

        meter = self._meter.detect(sample)
        rhyme = self._rhyme.detect(sample)

        self._logger.info(
            "Detection complete",
            meter=meter.meter if meter else None,
            feet=meter.foot_count if meter else None,
            scheme=rhyme.scheme if rhyme else None,
        )
        return DetectionResult(meter=meter, rhyme=rhyme)
