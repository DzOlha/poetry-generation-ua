"""ILineFeedbackBuilder implementation for meter validation results.

Extracted from `UkrainianProsodyAnalyzer` so the analyser stays focused on
rhythm logic while feedback construction becomes a pluggable concern. The
builder uses `LineMeterResult.annotation` (a data field) to pick up
validator-specific extras without any `isinstance` branching.
"""
from __future__ import annotations

from src.domain.feedback import LineFeedback
from src.domain.models import LineMeterResult, MeterSpec
from src.domain.ports import ILineFeedbackBuilder


class DefaultLineFeedbackBuilder(ILineFeedbackBuilder):
    """Builds `LineFeedback` DTOs using only fields on `LineMeterResult`."""

    def build(
        self,
        line_idx: int,
        meter: MeterSpec,
        result: LineMeterResult,
    ) -> LineFeedback:
        return LineFeedback(
            line_idx=line_idx,
            meter_name=meter.name,
            foot_count=meter.foot_count,
            expected_stresses=result.expected_stresses,
            actual_stresses=result.actual_stresses,
            total_syllables=result.total_syllables,
            extra_note=result.annotation,
        )
