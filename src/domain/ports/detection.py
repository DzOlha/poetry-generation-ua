"""Detection ports — interfaces for meter/rhyme auto-detection.

These ports abstract the brute-force detection strategy so the service
layer depends only on the contract, not on the iteration logic.
The ``IStanzaSampler`` is intentionally flexible: it accepts a
``line_count`` parameter so callers can sample 2, 3, 4, or 14 lines
(for future sonnet detection).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection


class IStanzaSampler(ABC):
    """Extracts a fixed number of leading non-empty lines from poem text.

    Designed for extensibility: ``line_count`` can be 2, 3, 4 (default),
    or 14 (for future sonnet compound-scheme detection).
    """

    @abstractmethod
    def sample(self, poem_text: str, line_count: int) -> str | None:
        """Return the first ``line_count`` non-empty lines joined by newlines.

        Returns ``None`` if the poem has fewer usable lines than requested.
        """


class IMeterDetector(ABC):
    """Identifies the best-matching meter and foot count for a text sample.

    Implementations try every supported meter × foot-count combination
    and return the one with the highest accuracy, or ``None`` if nothing
    exceeds the configured threshold.
    """

    @abstractmethod
    def detect(self, text: str) -> MeterDetection | None:
        """Return the best meter match, or None if below threshold."""


class IRhymeDetector(ABC):
    """Identifies the best-matching rhyme scheme for a text sample.

    Implementations try every supported rhyme pattern and return the one
    with the highest accuracy, or ``None`` if nothing exceeds the threshold.
    """

    @abstractmethod
    def detect(self, text: str) -> RhymeDetection | None:
        """Return the best rhyme scheme match, or None if below threshold."""


class IDetectionService(ABC):
    """Facade that combines stanza sampling, meter detection, and rhyme detection."""

    @abstractmethod
    def detect(self, poem_text: str, sample_lines: int | None = None) -> DetectionResult:
        """Detect meter and rhyme from the first ``sample_lines`` of the poem."""
