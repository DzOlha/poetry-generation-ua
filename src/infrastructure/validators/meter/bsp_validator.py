"""BSP-based Ukrainian meter validator.

Uses Bidirectional Stress Pyramid scoring. The BSP math is fully
encapsulated in `BSPAlgorithm` (SRP). Produces standard `LineMeterResult`
with BSP-specific data in the ``annotation`` field so feedback callers do
not need ``isinstance`` checks.
"""
from __future__ import annotations

from src.domain.models import LineMeterResult, MeterSpec
from src.domain.ports import (
    ILineFeedbackBuilder,
    IProsodyAnalyzer,
    ITextProcessor,
)
from src.infrastructure.validators.meter.base import BaseMeterValidator
from src.infrastructure.validators.meter.bsp_algorithm import (
    BSPAlgorithm,
    BSPIssue,
)


def _bsp_annotation(score: float, issues: tuple[BSPIssue, ...]) -> str:
    """Build the annotation string for a BSP result."""
    parts = [f" (BSP score: {score:.2f})"]
    if issues:
        parts.append(f" — {issues[0].message}")
    return "".join(parts)


class BSPMeterValidator(BaseMeterValidator):
    """Validates meter using Bidirectional Stress Pyramid scoring."""

    def __init__(
        self,
        prosody: IProsodyAnalyzer,
        text_processor: ITextProcessor,
        feedback_builder: ILineFeedbackBuilder,
        bsp_algorithm: BSPAlgorithm,
        score_threshold: float = 0.6,
        allowed_mismatches: int = 2,
    ) -> None:
        super().__init__(
            prosody=prosody,
            text_processor=text_processor,
            feedback_builder=feedback_builder,
            allowed_mismatches=allowed_mismatches,
        )
        self._threshold = score_threshold
        self._bsp: BSPAlgorithm = bsp_algorithm

    def _validate_line(self, line: str, meter: MeterSpec) -> LineMeterResult:
        tokens = self._text.tokenize_line(line)
        words = list(tokens.words)
        syllables = list(tokens.syllables_per_word)
        actual_pattern = self._prosody.actual_stress_pattern(words, syllables)
        expected_pattern = self._prosody.build_expected_pattern(meter.name, meter.foot_count)
        flags = self._prosody.syllable_word_flags(words, syllables)

        actual_bin = [1 if ch == "—" else 0 for ch in actual_pattern]
        expected_bin = [1 if ch == "—" else 0 for ch in expected_pattern]

        score = self._bsp.compute_score(actual_bin, expected_bin)
        issues = self._bsp.detect_errors(actual_bin, expected_bin, flags)
        length_ok = self._prosody.line_length_ok(actual_pattern, expected_pattern)

        hard_errors = [iss for iss in issues if iss.type in ("stress_missing", "stress_overflow")]
        ok = score >= self._threshold and len(hard_errors) <= self.allowed_mismatches and length_ok

        return LineMeterResult(
            ok=ok,
            expected_stresses=tuple(i + 1 for i, v in enumerate(expected_pattern) if v == "—"),
            actual_stresses=tuple(i + 1 for i, v in enumerate(actual_pattern) if v == "—"),
            error_positions=tuple(sorted({iss.position for iss in hard_errors})),
            total_syllables=len(actual_pattern),
            annotation=_bsp_annotation(score, tuple(issues)),
        )
