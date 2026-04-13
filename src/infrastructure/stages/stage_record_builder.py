"""`IStageRecordBuilder` implementation — builds StageRecord observability payloads.

Extracted from `ValidationStage` so the stage body shows the control flow
without being buried in serialisation code. This class owns all the
details of how a stage result is rendered into a `StageRecord` dict:
rounded scores, indexed meter/rhyme result lists, and the input/output
summary strings.
"""
from __future__ import annotations

from typing import Any

from src.domain.evaluation import StageRecord
from src.domain.models import (
    LineMeterResult,
    MeterResult,
    Poem,
    RhymePairResult,
    RhymeResult,
)
from src.domain.ports import IStageRecordBuilder


class DefaultStageRecordBuilder(IStageRecordBuilder):
    """Builds `StageRecord` payloads used by the validation stage."""

    STAGE_NAME_VALIDATION = "validation"

    def for_validation(
        self,
        poem_text: str,
        meter_result: MeterResult,
        rhyme_result: RhymeResult,
        duration_sec: float,
        *,
        feedback_messages: list[str] | None = None,
    ) -> StageRecord:
        parsed = Poem.from_text(poem_text)
        messages = feedback_messages if feedback_messages is not None else []
        return StageRecord(
            name=self.STAGE_NAME_VALIDATION,
            input_summary=f"poem ({parsed.line_count} lines)",
            output_summary=(
                f"meter_acc={meter_result.accuracy:.2%}, "
                f"rhyme_acc={rhyme_result.accuracy:.2%}, "
                f"violations={len(messages)}"
            ),
            output_data={
                "meter_results": [
                    self._meter_line_dict(i, r)
                    for i, r in enumerate(meter_result.line_results)
                ],
                "rhyme_results": [
                    self._rhyme_pair_dict(p) for p in rhyme_result.pair_results
                ],
                "feedback": messages,
            },
            metrics={
                "meter_accuracy": meter_result.accuracy,
                "rhyme_accuracy": rhyme_result.accuracy,
                "violation_count": len(messages),
            },
            duration_sec=duration_sec,
        )

    @staticmethod
    def _meter_line_dict(idx: int, r: LineMeterResult) -> dict[str, Any]:
        return {
            "line": idx + 1,
            "ok": r.ok,
            "expected_stress": r.expected_stresses,
            "actual_stress": r.actual_stresses,
            "error_positions": r.error_positions,
            "total_syllables": r.total_syllables,
        }

    @staticmethod
    def _rhyme_pair_dict(p: RhymePairResult) -> dict[str, Any]:
        return {
            "line_a": p.line_a_idx + 1,
            "line_b": p.line_b_idx + 1,
            "word_a": p.word_a,
            "word_b": p.word_b,
            "rhyme_part_a": p.rhyme_part_a,
            "rhyme_part_b": p.rhyme_part_b,
            "score": round(p.score, 4),
            "ok": p.ok,
        }
