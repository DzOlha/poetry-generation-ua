"""Prosody analysis ports."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.feedback import LineFeedback
from src.domain.models import LineMeterResult, MeterSpec


class IMeterTemplateProvider(ABC):
    """Returns the canonical syllable-stress template for a meter name."""

    @abstractmethod
    def template_for(self, meter_name: str) -> list[str]: ...

    @abstractmethod
    def supported_meters(self) -> tuple[str, ...]: ...


class IWeakStressLexicon(ABC):
    """Knows which words may carry no metric stress (function words, particles)."""

    @abstractmethod
    def is_weak(self, word: str) -> bool: ...


class ISyllableFlagStrategy(ABC):
    """Computes per-syllable (is_monosyllabic, is_weak) flags for a line."""

    @abstractmethod
    def flags(
        self,
        words: list[str],
        syllables_per_word: list[int],
    ) -> list[tuple[bool, bool]]: ...


class IStressPatternAnalyzer(ABC):
    """Derives the actual realised stress pattern from a tokenised line."""

    @abstractmethod
    def actual_stress_pattern(
        self,
        words: list[str],
        syllables_per_word: list[int],
    ) -> list[str]: ...

    @abstractmethod
    def syllable_word_flags(
        self,
        words: list[str],
        syllables_per_word: list[int],
    ) -> list[tuple[bool, bool]]: ...


class IExpectedMeterBuilder(ABC):
    """Builds the canonical expected stress pattern for a given meter + foot count."""

    @abstractmethod
    def build_expected_pattern(self, meter: str, foot_count: int) -> list[str]: ...


class IMismatchTolerance(ABC):
    """Decides which stress-pattern mismatches a validator may ignore."""

    @abstractmethod
    def line_length_ok(
        self,
        actual_pattern: list[str],
        expected_pattern: list[str],
    ) -> bool: ...

    @abstractmethod
    def is_tolerated_mismatch(
        self,
        pos: int,
        actual: list[str],
        expected: list[str],
        flags: list[tuple[bool, bool]],
    ) -> bool: ...


class IProsodyAnalyzer(
    IStressPatternAnalyzer,
    IExpectedMeterBuilder,
    IMismatchTolerance,
):
    """Facade union of the three focused prosody ports.

    Kept as a marker interface so existing callers that legitimately need
    the full surface (validators, line-feedback builder) can still depend
    on one type. New code should prefer the narrower ports above.
    """


class ILineFeedbackBuilder(ABC):
    """Builds a structured `LineFeedback` for a failing validator line result."""

    @abstractmethod
    def build(
        self,
        line_idx: int,
        meter: MeterSpec,
        result: LineMeterResult,
    ) -> LineFeedback: ...
