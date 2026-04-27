"""Prosody analysis ports."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import LineMeterResult, MeterSpec
from src.domain.models.feedback import LineFeedback


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
    """**Deprecated for new code.**  Facade union of three focused ports.

    The architectural audit flagged this union as an Interface Segregation
    smell — most callers only need one of the three sub-ports, but
    depending on ``IProsodyAnalyzer`` forces them to know about (and mock)
    the whole surface. Existing callers that legitimately want the full
    surface (BSP/pattern meter validators, the line-feedback builder)
    continue to use it, but new code MUST depend on the narrowest port
    that satisfies its actual contract:

      - ``IStressPatternAnalyzer``  — for line-level stress derivation
      - ``IExpectedMeterBuilder``   — for canonical-pattern lookup
      - ``IMismatchTolerance``      — for ignoring acceptable deviations
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
