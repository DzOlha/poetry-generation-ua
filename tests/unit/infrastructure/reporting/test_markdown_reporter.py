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

    def test_renders_generation_model_section_when_configured(self):
        reporter = MarkdownReporter(
            llm_provider="gemini", llm_model="gemini-2.0-flash",
        )
        md = reporter.format_markdown_report([_summary()], [_trace()])
        assert "## Generation Model" in md
        assert "**Provider**: gemini" in md
        assert "**Model**: gemini-2.0-flash" in md

    def test_omits_generation_model_section_when_nothing_configured(self):
        md = MarkdownReporter().format_markdown_report([_summary()], [_trace()])
        assert "## Generation Model" not in md

    def test_renders_config_legend_from_descriptions(self):
        reporter = MarkdownReporter(
            config_descriptions={"A": "Baseline (no RAG)", "B": "With feedback"},
        )
        md = reporter.format_markdown_report([_summary("A"), _summary("B")], [_trace()])
        assert "## Config Legend" in md
        assert "**A** — Baseline (no RAG)" in md
        assert "**B** — With feedback" in md

    def test_legend_omitted_when_no_descriptions(self):
        md = MarkdownReporter().format_markdown_report([_summary("A")], [_trace()])
        assert "## Config Legend" not in md

    def test_summary_table_includes_config_description_column(self):
        reporter = MarkdownReporter(config_descriptions={"A": "Baseline run"})
        md = reporter.format_summary_table([_summary("A")])
        assert "Config Description" in md
        assert "Baseline run" in md


class TestIntermediatePoems:
    def test_renders_per_iteration_poem_block(self):
        detail = MarkdownReporter().format_trace_detail(_trace())
        assert "Intermediate poems (per iteration)" in detail
        assert "[iter 0]" in detail
        # poem_text was "вірш" — a single clean line that must appear
        assert "| вірш" in detail

    def test_iteration_poem_filters_scansion(self):
        # Intermediate poems go through Poem.from_text → scansion stripped.
        trace = PipelineTrace(
            scenario_id="N01",
            config_label="A",
            stages=(),
            iterations=(
                IterationRecord(
                    iteration=1,
                    poem_text="добрий рядок\nСЛА-ва У-КРА-ї-НІ\nінший рядок",
                    meter_accuracy=1.0, rhyme_accuracy=1.0,
                    feedback=(), duration_sec=0.01,
                ),
            ),
            final_poem="final",
            final_metrics={},
            total_duration_sec=0.1,
        )
        detail = MarkdownReporter().format_trace_detail(trace)
        assert "| добрий рядок" in detail
        assert "| інший рядок" in detail
        assert "СЛА-ва" not in detail  # scansion stripped from rendered block

    def test_reports_empty_when_all_lines_filtered(self):
        trace = PipelineTrace(
            scenario_id="N01", config_label="A", stages=(),
            iterations=(
                IterationRecord(
                    iteration=1, poem_text="1 2 3 4\n(u) (u) ( - )",
                    meter_accuracy=0.0, rhyme_accuracy=0.0,
                    feedback=(), duration_sec=0.0,
                ),
            ),
            final_poem="", final_metrics={}, total_duration_sec=0.0,
        )
        detail = MarkdownReporter().format_trace_detail(trace)
        assert "(empty / unparsable)" in detail
