"""Unit tests for NullTracer."""
from __future__ import annotations

from src.domain.evaluation import IterationRecord, PipelineTrace
from src.infrastructure.tracing import NullTracer


class TestNullTracer:
    def test_final_poem_roundtrip(self):
        t = NullTracer()
        t.set_final_poem("текст")
        assert t.get_trace().final_poem == "текст"

    def test_iterations_accumulated(self):
        t = NullTracer()
        rec = IterationRecord(
            iteration=0, poem_text="", meter_accuracy=0.5, rhyme_accuracy=0.5,
            feedback=(),
        )
        t.add_iteration(rec)
        assert t.iterations() == (rec,)

    def test_error_is_recorded(self):
        t = NullTracer()
        t.set_error("boom")
        assert t.get_trace().error == "boom"

    def test_snapshot_is_pipeline_trace(self):
        assert isinstance(NullTracer().get_trace(), PipelineTrace)

    def test_add_stage_is_a_noop(self):
        from src.domain.evaluation import StageRecord

        t = NullTracer()
        t.add_stage(StageRecord(name="x"))
        assert t.get_trace().stages == ()
