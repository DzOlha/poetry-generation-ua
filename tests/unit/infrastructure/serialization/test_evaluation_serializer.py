"""Tests for evaluation serialization functions."""
from __future__ import annotations

from src.domain.evaluation import (
    EvaluationSummary,
    IterationRecord,
    PipelineTrace,
    StageRecord,
)
from src.infrastructure.serialization.evaluation_serializer import (
    evaluation_summary_to_dict,
    iteration_record_to_dict,
    pipeline_trace_to_dict,
    stage_record_to_dict,
)


class TestEvaluationSummaryToDict:
    def test_all_fields_present(self):
        s = EvaluationSummary(
            scenario_id="N1",
            scenario_name="Test",
            config_label="A",
            meter="ямб",
            foot_count=4,
            rhyme_scheme="ABAB",
            meter_accuracy=0.85714,
            rhyme_accuracy=0.66666,
            num_iterations=3,
            num_lines=8,
            duration_sec=1.23456,
        )
        d = evaluation_summary_to_dict(s)
        assert d["scenario_id"] == "N1"
        assert d["config"] == "A"
        assert d["meter_accuracy"] == 0.8571
        assert d["rhyme_accuracy"] == 0.6667
        assert d["duration_sec"] == 1.2346
        assert d["error"] is None

    def test_error_field_preserved(self):
        s = EvaluationSummary(
            scenario_id="N1", scenario_name="Test", config_label="A",
            meter="ямб", foot_count=4, rhyme_scheme="ABAB",
            meter_accuracy=0.0, rhyme_accuracy=0.0,
            num_iterations=0, num_lines=0, duration_sec=0.0,
            error="LLM timeout",
        )
        d = evaluation_summary_to_dict(s)
        assert d["error"] == "LLM timeout"


class TestStageRecordToDict:
    def test_minimal_record(self):
        rec = StageRecord(name="validation", duration_sec=0.12345)
        d = stage_record_to_dict(rec)
        assert d["stage"] == "validation"
        assert d["duration_sec"] == 0.1235
        assert "input_data" not in d
        assert "output_data" not in d
        assert "error" not in d

    def test_optional_fields_included_when_set(self):
        rec = StageRecord(
            name="retrieval",
            input_summary="theme: весна",
            output_summary="5 excerpts",
            input_data={"theme": "весна"},
            output_data=[{"title": "poem1"}],
            duration_sec=0.5,
            error="partial failure",
        )
        d = stage_record_to_dict(rec)
        assert d["input_data"] == {"theme": "весна"}
        assert d["output_data"] == [{"title": "poem1"}]
        assert d["error"] == "partial failure"


class TestIterationRecordToDict:
    def test_rounds_floats(self):
        rec = IterationRecord(
            iteration=1,
            poem_text="Рядок вірша",
            meter_accuracy=0.87654,
            rhyme_accuracy=0.99999,
            feedback=("fix line 1",),
            duration_sec=2.56789,
        )
        d = iteration_record_to_dict(rec)
        assert d["iteration"] == 1
        assert d["meter_accuracy"] == 0.8765
        assert d["rhyme_accuracy"] == 1.0
        assert d["duration_sec"] == 2.5679
        assert d["feedback"] == ("fix line 1",)


class TestPipelineTraceToDict:
    def test_empty_trace(self):
        t = PipelineTrace(scenario_id="N1", config_label="A")
        d = pipeline_trace_to_dict(t)
        assert d["scenario_id"] == "N1"
        assert d["stages"] == []
        assert d["iterations"] == []
        assert d["final_poem"] == ""
        assert "error" not in d

    def test_trace_with_stages_and_iterations(self):
        stage = StageRecord(name="generation", duration_sec=1.0)
        iteration = IterationRecord(
            iteration=0, poem_text="text",
            meter_accuracy=0.5, rhyme_accuracy=0.5,
            feedback=(), duration_sec=0.1,
        )
        t = PipelineTrace(
            scenario_id="N1", config_label="E",
            stages=(stage,),
            iterations=(iteration,),
            final_poem="final text",
            final_metrics={"meter_accuracy": 0.85714, "lines": 4},
            total_duration_sec=3.14159,
        )
        d = pipeline_trace_to_dict(t)
        assert len(d["stages"]) == 1
        assert d["stages"][0]["stage"] == "generation"
        assert len(d["iterations"]) == 1
        assert d["final_poem"] == "final text"
        assert d["final_metrics"]["meter_accuracy"] == 0.8571
        assert d["final_metrics"]["lines"] == 4  # int not rounded
        assert d["total_duration_sec"] == 3.1416

    def test_trace_with_error(self):
        t = PipelineTrace(
            scenario_id="N1", config_label="A",
            error="LLM failure",
            total_duration_sec=0.0,
        )
        d = pipeline_trace_to_dict(t)
        assert d["error"] == "LLM failure"
