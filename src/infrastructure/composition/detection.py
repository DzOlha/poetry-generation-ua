"""Detection sub-container — stanza sampler, meter detector, rhyme detector."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports.detection import (
    IMeterDetector,
    IRhymeDetector,
    IStanzaSampler,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.detection import (
    BruteForceMeterDetector,
    BruteForceRhymeDetector,
    FirstLinesStanzaSampler,
)

if TYPE_CHECKING:
    from src.composition_root import Container


class DetectionSubContainer:
    """Stanza sampler + brute-force meter/rhyme detectors."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def stanza_sampler(self) -> IStanzaSampler:
        return self._parent._get(
            CacheKey.STANZA_SAMPLER,
            lambda: FirstLinesStanzaSampler(
                line_splitter=self._parent.text_processor(),
            ),
        )

    def meter_detector(self) -> IMeterDetector:
        return self._parent._get(
            CacheKey.METER_DETECTOR,
            lambda: BruteForceMeterDetector(
                meter_validator=self._parent.meter_validator(),
                config=self._parent.config.detection,
            ),
        )

    def rhyme_detector(self) -> IRhymeDetector:
        return self._parent._get(
            CacheKey.RHYME_DETECTOR,
            lambda: BruteForceRhymeDetector(
                rhyme_validator=self._parent.rhyme_validator(),
                config=self._parent.config.detection,
            ),
        )
