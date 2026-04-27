"""Result objects — validator and service outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.domain.models.aggregates import Poem
from src.domain.value_objects import ClausulaType, RhymePrecision

if TYPE_CHECKING:
    from src.domain.models.feedback import LineFeedback, PairFeedback


@dataclass(frozen=True)
class IterationSnapshot:
    """Per-iteration snapshot surfaced through the service/API boundary.

    Mirrors `IterationRecord` but lives in `domain.models` so handlers and
    frontends can consume generation history without importing evaluation
    internals.
    """

    iteration: int
    poem: str
    meter_accuracy: float
    rhyme_accuracy: float
    feedback: tuple[str, ...] = ()
    duration_sec: float = 0.0
    # Debug trace: raw provider output and post-sanitizer text for the
    # LLM call that produced this iteration. Empty when the snapshot
    # originates from a test double that bypasses the decorator stack.
    raw_llm_response: str = ""
    sanitized_llm_response: str = ""


@dataclass(frozen=True)
class LineMeterResult:
    """Raw meter check for a single line, produced by IMeterValidator internals."""

    ok: bool
    expected_stresses: tuple[int, ...]    # 1-based syllable positions
    actual_stresses: tuple[int, ...]      # 1-based syllable positions
    error_positions: tuple[int, ...]      # 1-based syllable positions
    total_syllables: int
    annotation: str = ""


@dataclass(frozen=True)
class RhymePairResult:
    """Raw rhyme check for a pair of lines, produced by IRhymeValidator internals."""

    line_a_idx: int
    line_b_idx: int
    word_a: str
    word_b: str
    rhyme_part_a: str
    rhyme_part_b: str
    score: float
    ok: bool
    clausula_a: ClausulaType = ClausulaType.UNKNOWN
    clausula_b: ClausulaType = ClausulaType.UNKNOWN
    precision: RhymePrecision = RhymePrecision.NONE


@dataclass(frozen=True)
class MeterResult:
    """Aggregated meter validation result for an entire poem."""

    ok: bool
    accuracy: float
    feedback: tuple[LineFeedback, ...] = ()
    line_results: tuple[LineMeterResult, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class RhymeResult:
    """Aggregated rhyme validation result for an entire poem."""

    ok: bool
    accuracy: float
    feedback: tuple[PairFeedback, ...] = ()
    pair_results: tuple[RhymePairResult, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class ValidationResult:
    """Combined meter + rhyme validation result."""

    meter: MeterResult
    rhyme: RhymeResult
    iterations: int = 0

    @property
    def is_valid(self) -> bool:
        return self.meter.ok and self.rhyme.ok

    @property
    def feedback(self) -> tuple[LineFeedback | PairFeedback, ...]:
        return self.meter.feedback + self.rhyme.feedback


@dataclass(frozen=True)
class GenerationResult:
    """Final output of the poem generation pipeline."""

    poem: str
    validation: ValidationResult
    iteration_history: tuple[IterationSnapshot, ...] = ()

    @property
    def poem_object(self) -> Poem:
        """Return the generated poem as a parsed `Poem` aggregate."""
        return Poem.from_text(self.poem)
