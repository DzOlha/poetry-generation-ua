"""Tests for DefaultPoemGenerationPipeline."""
from __future__ import annotations

import pytest

from src.domain.errors import LLMError, LLMQuotaExceededError
from src.domain.evaluation import IterationRecord
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

    def test_iteration_history_surfaced_from_tracer(self):
        # Handlers (and the web UI) need access to intermediate drafts so the
        # "feedback iterations" table can show each attempted poem. The
        # pipeline adapts tracer.iterations() into an `IterationSnapshot`
        # tuple on the `GenerationResult`; regression-guard that mapping.
        records = (
            IterationRecord(
                iteration=0,
                poem_text="draft 0",
                meter_accuracy=0.5,
                rhyme_accuracy=1.0,
                feedback=("fix line 2",),
                duration_sec=0.8,
            ),
            IterationRecord(
                iteration=1,
                poem_text="draft 1 (final)",
                meter_accuracy=1.0,
                rhyme_accuracy=1.0,
                feedback=(),
                duration_sec=28.9,
            ),
        )

        class _TracingPipeline(IPipeline):
            def run(self, state: PipelineState) -> None:
                state.poem = "draft 1 (final)"
                state.last_meter_result = MeterResult(ok=True, accuracy=1.0)
                state.last_rhyme_result = RhymeResult(ok=True, accuracy=1.0)
                for rec in records:
                    state.tracer.add_iteration(rec)

        service = DefaultPoemGenerationPipeline(
            pipeline=_TracingPipeline(), logger=NullLogger(),
        )
        result = service.build(_request())

        assert len(result.iteration_history) == 2
        assert [s.iteration for s in result.iteration_history] == [0, 1]
        assert result.iteration_history[0].poem == "draft 0"
        assert result.iteration_history[0].meter_accuracy == 0.5
        assert result.iteration_history[0].feedback == ("fix line 2",)
        assert result.iteration_history[1].poem == "draft 1 (final)"
        assert result.validation.iterations == 1  # one feedback pass after the seed

    def test_iteration_history_empty_when_tracer_silent(self):
        pipeline = _RecordingPipeline("рядок", meter_ok=True, rhyme_ok=True)
        result = DefaultPoemGenerationPipeline(
            pipeline=pipeline, logger=NullLogger(),
        ).build(_request())
        assert result.iteration_history == ()

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


class TestAbortPropagation:
    """A stage that catches a DomainError and marks `state.aborted=True`
    must surface that to the caller — otherwise /generate silently returns
    an empty poem with 0% metrics (the C05 quota / CoT-only failure UX).
    """

    def test_aborted_run_reraises_original_exception(self):
        original = LLMQuotaExceededError("Daily limit of 250 requests reached.")

        class _AbortingPipeline(IPipeline):
            def run(self, state: PipelineState) -> None:
                state.abort("generation failed: quota", exception=original)

        service = DefaultPoemGenerationPipeline(
            pipeline=_AbortingPipeline(), logger=NullLogger(),
        )
        with pytest.raises(LLMQuotaExceededError) as exc_info:
            service.build(_request())
        assert exc_info.value is original  # exact instance preserved

    def test_aborted_run_without_exception_raises_llm_error_with_reason(self):
        class _AbortingPipeline(IPipeline):
            def run(self, state: PipelineState) -> None:
                state.abort("safety filter blocked output")

        service = DefaultPoemGenerationPipeline(
            pipeline=_AbortingPipeline(), logger=NullLogger(),
        )
        with pytest.raises(LLMError) as exc_info:
            service.build(_request())
        assert "safety filter" in str(exc_info.value)
