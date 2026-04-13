"""Tests for DefaultPoemGenerationPipeline."""
from __future__ import annotations

from src.domain.models import (
    GenerationRequest,
    MeterResult,
    MeterSpec,
    PoemStructure,
    RhymeResult,
    RhymeScheme,
)
from src.domain.pipeline_context import PipelineState
from src.domain.ports import IPipeline
from src.infrastructure.logging import NullLogger
from src.infrastructure.pipeline import DefaultPoemGenerationPipeline


class _RecordingPipeline(IPipeline):
    """Fake pipeline that records the state and synthesises a canned result."""

    def __init__(self, poem: str, meter_ok: bool, rhyme_ok: bool) -> None:
        self._poem = poem
        self._meter_ok = meter_ok
        self._rhyme_ok = rhyme_ok
        self.received: PipelineState | None = None

    def run(self, state: PipelineState) -> None:
        self.received = state
        state.poem = self._poem
        state.last_meter_result = MeterResult(
            ok=self._meter_ok, accuracy=1.0 if self._meter_ok else 0.0,
        )
        state.last_rhyme_result = RhymeResult(
            ok=self._rhyme_ok, accuracy=1.0 if self._rhyme_ok else 0.0,
        )


def _request() -> GenerationRequest:
    return GenerationRequest(
        theme="весна",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
        max_iterations=1,
    )


class TestDefaultPoemGenerationPipeline:
    def test_returns_generation_result_with_validation(self):
        pipeline = _RecordingPipeline("рядок один\n", meter_ok=True, rhyme_ok=True)
        service = DefaultPoemGenerationPipeline(pipeline=pipeline, logger=NullLogger())
        result = service.build(_request())
        assert result.poem == "рядок один\n"
        assert result.validation.is_valid

    def test_state_uses_default_generation_config(self):
        pipeline = _RecordingPipeline("", meter_ok=True, rhyme_ok=True)
        DefaultPoemGenerationPipeline(pipeline=pipeline, logger=NullLogger()).build(_request())
        assert pipeline.received is not None
        assert pipeline.received.config.label == "generate"

    def test_missing_validation_results_produce_failing_default(self):
        class _NoopPipeline(IPipeline):
            def run(self, state: PipelineState) -> None:
                state.poem = "рядок"

        service = DefaultPoemGenerationPipeline(
            pipeline=_NoopPipeline(),
            logger=NullLogger(),
        )
        result = service.build(_request())
        assert result.validation.meter.ok is False
        assert result.validation.rhyme.ok is False
