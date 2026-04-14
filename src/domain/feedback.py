"""Structured feedback value objects.

Validator feedback used to be plain strings parsed by downstream code via
regex. This module replaces that with typed objects so consumers (PoetryService
merger, MarkdownReporter, LLM prompts) can read structured data directly.

LineFeedback  — one meter violation for a single line
PairFeedback  — one rhyme violation between two lines

An IFeedbackFormatter implementation is responsible for rendering these
objects into the natural-language strings the LLM sees.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.value_objects import ClausulaType, RhymePrecision


@dataclass(frozen=True)
class LineFeedback:
    """Structured meter violation for a single poem line.

    Attributes:
        line_idx: 0-based index of the failing line within the poem.
        meter_name: Canonical meter this line was checked against.
        foot_count: Expected number of metrical feet.
        expected_stresses: 1-based syllable positions that should be stressed.
        actual_stresses: 1-based syllable positions that are stressed.
        total_syllables: Observed syllable count for the line.
        expected_syllables: Canonical syllable count for the expected meter template.
        extra_note: Optional validator-specific annotation (e.g. BSP score).
    """

    line_idx: int
    meter_name: str
    foot_count: int
    expected_stresses: tuple[int, ...]
    actual_stresses: tuple[int, ...]
    total_syllables: int
    expected_syllables: int = 0
    extra_note: str = ""


@dataclass(frozen=True)
class PairFeedback:
    """Structured rhyme violation for two lines that should rhyme.

    Attributes:
        line_a_idx: 0-based index of the first line in the failing pair.
        line_b_idx: 0-based index of the second line in the failing pair.
        scheme_pattern: Rhyme-scheme pattern the pair is derived from.
        word_a: Last word of line A.
        word_b: Last word of line B.
        rhyme_part_a: IPA suffix of word A from the stressed vowel onward.
        rhyme_part_b: IPA suffix of word B from the stressed vowel onward.
        score: Normalised Levenshtein similarity in [0, 1].
    """

    line_a_idx: int
    line_b_idx: int
    scheme_pattern: str
    word_a: str
    word_b: str
    rhyme_part_a: str
    rhyme_part_b: str
    score: float
    clausula_a: ClausulaType = ClausulaType.UNKNOWN
    clausula_b: ClausulaType = ClausulaType.UNKNOWN
    precision: RhymePrecision = RhymePrecision.NONE


def format_all_feedback(
    formatter: object,
    line_fbs: tuple[LineFeedback, ...],
    pair_fbs: tuple[PairFeedback, ...],
) -> list[str]:
    """Render every piece of feedback via *formatter*, meter first then rhyme.

    Accepts any object with ``format_line`` and ``format_pair`` methods
    (i.e. any ``IFeedbackFormatter`` implementation). The *formatter*
    parameter is typed as ``object`` to avoid a circular import between
    this module and ``ports.prompts`` — at runtime the duck-typed call is
    safe because every caller passes an ``IFeedbackFormatter``.
    """
    return [formatter.format_line(f) for f in line_fbs] + [formatter.format_pair(f) for f in pair_fbs]  # type: ignore[attr-defined]
