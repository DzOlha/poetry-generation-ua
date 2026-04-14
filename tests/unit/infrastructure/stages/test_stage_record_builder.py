"""Unit tests for `DefaultStageRecordBuilder`.

Covers the translation of validator results into `StageRecord` payloads:
summary strings, per-line/per-pair dicts, rounding, and metrics.
"""
from __future__ import annotations

from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.models import (
    LineMeterResult,
    MeterResult,
    RhymePairResult,
    RhymeResult,
)
from src.infrastructure.stages.stage_record_builder import DefaultStageRecordBuilder


def _make_meter_result() -> MeterResult:
    return MeterResult(
        ok=False,
        accuracy=0.75,
        line_results=(
            LineMeterResult(
                ok=True,
                expected_stresses=(2, 4,),
                actual_stresses=(2, 4,),
                error_positions=(),
                total_syllables=4,
            ),
            LineMeterResult(
                ok=False,
                expected_stresses=(2, 4,),
                actual_stresses=(1, 4,),
                error_positions=(1,),
                total_syllables=4,
            ),
        ),
        feedback=(
            LineFeedback(
                line_idx=1,
                meter_name="ямб",
                foot_count=2,
                expected_stresses=(2, 4),
                actual_stresses=(1, 4),
                total_syllables=4,
            ),
        ),
    )


def _make_rhyme_result() -> RhymeResult:
    return RhymeResult(
        ok=False,
        accuracy=0.875,
        pair_results=(
            RhymePairResult(
                line_a_idx=0,
                line_b_idx=2,
                word_a="ліс",
                word_b="ріс",
                rhyme_part_a="іс",
                rhyme_part_b="іс",
                score=0.95123,
                ok=True,
            ),
        ),
        feedback=(
            PairFeedback(
                line_a_idx=1,
                line_b_idx=3,
                scheme_pattern="ABAB",
                word_a="небо",
                word_b="слово",
                rhyme_part_a="ебо",
                rhyme_part_b="ово",
                score=0.2,
            ),
        ),
    )


class TestDefaultStageRecordBuilder:
    def test_returns_stage_record_with_validation_name(self) -> None:
        builder = DefaultStageRecordBuilder()
        record = builder.for_validation(
            poem_text="а\nб\nв\nг\n",
            meter_result=_make_meter_result(),
            rhyme_result=_make_rhyme_result(),
            duration_sec=1.25,
        )
        assert record.name == "validation"
        assert record.duration_sec == 1.25

    def test_summary_strings_include_line_count_and_accuracies(self) -> None:
        builder = DefaultStageRecordBuilder()
        record = builder.for_validation(
            poem_text="а\nб\nв\nг\n",
            meter_result=_make_meter_result(),
            rhyme_result=_make_rhyme_result(),
            duration_sec=0.1,
            feedback_messages=["msg1", "msg2"],
        )
        assert "4 lines" in record.input_summary
        assert "75.00%" in record.output_summary
        assert "87.50%" in record.output_summary
        assert "violations=2" in record.output_summary

    def test_output_data_contains_meter_and_rhyme_lists(self) -> None:
        builder = DefaultStageRecordBuilder()
        record = builder.for_validation(
            poem_text="а\nб\n",
            meter_result=_make_meter_result(),
            rhyme_result=_make_rhyme_result(),
            duration_sec=0.0,
            feedback_messages=["x"],
        )
        data = record.output_data
        assert "meter_results" in data
        assert len(data["meter_results"]) == 2
        # Indices should be 1-based in serialised output
        assert data["meter_results"][0]["line"] == 1
        assert data["meter_results"][1]["ok"] is False
        assert "rhyme_results" in data
        assert data["rhyme_results"][0]["line_a"] == 1  # 0 -> 1
        assert data["rhyme_results"][0]["line_b"] == 3  # 2 -> 3
        assert data["rhyme_results"][0]["score"] == 0.9512  # rounded to 4 places
        assert data["feedback"] == ["x"]

    def test_metrics_reflect_raw_accuracies(self) -> None:
        builder = DefaultStageRecordBuilder()
        record = builder.for_validation(
            poem_text="а\nб\n",
            meter_result=_make_meter_result(),
            rhyme_result=_make_rhyme_result(),
            duration_sec=0.0,
            feedback_messages=[],
        )
        m = record.metrics
        assert m["meter_accuracy"] == 0.75
        assert m["rhyme_accuracy"] == 0.875
        assert m["violation_count"] == 0

    def test_missing_feedback_messages_treats_as_empty(self) -> None:
        builder = DefaultStageRecordBuilder()
        record = builder.for_validation(
            poem_text="a\n",
            meter_result=_make_meter_result(),
            rhyme_result=_make_rhyme_result(),
            duration_sec=0.0,
        )
        assert record.metrics["violation_count"] == 0
        assert record.output_data["feedback"] == []
