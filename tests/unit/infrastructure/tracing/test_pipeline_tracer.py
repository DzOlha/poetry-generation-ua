"""Tests for PipelineTracer and PipelineTracerFactory."""
from __future__ import annotations

from src.domain.evaluation import IterationRecord, PipelineTrace, StageRecord
from src.infrastructure.tracing import PipelineTracer, PipelineTracerFactory


class TestPipelineTracer:
    def test_empty_trace(self):
        tracer = PipelineTracer(scenario_id="N01", config_label="A")
        trace = tracer.get_trace()
        assert isinstance(trace, PipelineTrace)
        assert trace.scenario_id == "N01"
        assert trace.config_label == "A"
        assert trace.stages == ()
        assert trace.iterations == ()

    def test_add_stage_appends(self):
        tracer = PipelineTracer("N01", "A")
        tracer.add_stage(StageRecord(name="retrieval"))
        tracer.add_stage(StageRecord(name="generation"))
        assert [s.name for s in tracer.get_trace().stages] == ["retrieval", "generation"]

    def test_add_iteration_appends(self):
        tracer = PipelineTracer("N01", "A")
        tracer.add_iteration(IterationRecord(
            iteration=0, poem_text="", meter_accuracy=0.0,
            rhyme_accuracy=0.0, feedback=(),
        ))
        assert len(tracer.get_trace().iterations) == 1

    def test_get_trace_returns_immutable_snapshot(self):
        tracer = PipelineTracer("N01", "A")
        snap1 = tracer.get_trace()
        tracer.add_stage(StageRecord(name="late"))
        snap2 = tracer.get_trace()
        assert len(snap1.stages) == 0
        assert len(snap2.stages) == 1

    def test_set_final_metrics_and_poem(self):
        tracer = PipelineTracer("N01", "A")
        tracer.set_final_poem("hello")
        tracer.set_final_metrics({"meter_accuracy": 0.9})
        tracer.set_total_duration(1.5)
        trace = tracer.get_trace()
        assert trace.final_poem == "hello"
        assert trace.final_metrics == {"meter_accuracy": 0.9}
        assert trace.total_duration_sec == 1.5


class TestPipelineTracerFactory:
    def test_creates_new_instances(self):
        factory = PipelineTracerFactory()
        a = factory.create("N01", "A")
        b = factory.create("N01", "A")
        assert a is not b
        a.add_stage(StageRecord(name="retrieval"))
        assert len(b.get_trace().stages) == 0
