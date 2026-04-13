"""Tests for MarkdownReporter."""
from __future__ import annotations

from src.domain.evaluation import (
    EvaluationSummary,
    IterationRecord,
    PipelineTrace,
    StageRecord,
)
from src.infrastructure.reporting import MarkdownReporter


def _summary(label: str = "A", error: str | None = None) -> EvaluationSummary:
    return EvaluationSummary(
        scenario_id="N01",
        scenario_name="Test scenario",
        config_label=label,
        meter="ямб",
        foot_count=4,
        rhyme_scheme="ABAB",
        meter_accuracy=0.75,
        rhyme_accuracy=0.5,
        num_iterations=2,
        num_lines=4,
        duration_sec=1.23,
        error=error,
    )


def _trace() -> PipelineTrace:
    return PipelineTrace(
        scenario_id="N01",
        config_label="A",
        stages=(
            StageRecord(
                name="retrieval",
                input_summary="theme=весна",
                output_summary="2 poems",
                metrics={"num_retrieved": 2},
                duration_sec=0.01,
            ),
        ),
        iterations=(
            IterationRecord(
                iteration=0, poem_text="вірш", meter_accuracy=0.5,
                rhyme_accuracy=0.5, feedback=("fb",), duration_sec=0.01,
            ),
        ),
        final_poem="рядок один\nрядок два",
        final_metrics={"meter_accuracy": 0.5, "rhyme_accuracy": 0.5},
        total_duration_sec=1.0,
    )


class TestFormatSummaryTable:
    def test_contains_header(self):
        table = MarkdownReporter().format_summary_table([_summary()])
        assert "Scenario" in table
        assert "Meter%" in table
        assert "Rhyme%" in table

    def test_shows_error_column(self):
        table = MarkdownReporter().format_summary_table([_summary(error="boom")])
        assert "boom" in table

    def test_placeholder_for_no_error(self):
        table = MarkdownReporter().format_summary_table([_summary()])
        # Has an em-dash placeholder in the Error column for success rows.
        assert "—" in table


class TestFormatTraceDetail:
    def test_contains_scenario_id(self):
        detail = MarkdownReporter().format_trace_detail(_trace())
        assert "scenario=N01" in detail
        assert "config=A" in detail

    def test_contains_stage_names(self):
        detail = MarkdownReporter().format_trace_detail(_trace())
        assert "retrieval" in detail

    def test_contains_final_poem(self):
        detail = MarkdownReporter().format_trace_detail(_trace())
        assert "рядок один" in detail


class TestFormatMarkdownReport:
    def test_contains_summary_and_trace(self):
        md = MarkdownReporter().format_markdown_report([_summary()], [_trace()])
        assert "# Evaluation Report" in md
        assert "## Summary" in md
        assert "## Trace Details" in md
        assert "## Aggregate by Config" in md
        assert "рядок один" in md
