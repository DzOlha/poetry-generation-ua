"""DefaultPoemGenerationPipeline — IPoemGenerationPipeline implementation.

Drives the same `IPipeline` + stage chain used by evaluation, but with a
`NullTracer` and the `DEFAULT_GENERATION_CONFIG` ablation profile so
`PoetryService.generate` never duplicates orchestration code. The result
comes out as a `GenerationResult` ready for handlers and runners.
"""
from __future__ import annotations

from src.domain.evaluation import DEFAULT_GENERATION_CONFIG
from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    IterationSnapshot,
    MeterResult,
    RhymeResult,
    ValidationResult,
)
from src.domain.pipeline_context import PipelineState
from src.domain.ports import ILogger, IPipeline, IPoemGenerationPipeline
from src.infrastructure.tracing.null_tracer import NullTracer


class DefaultPoemGenerationPipeline(IPoemGenerationPipeline):
    """Runs the shared `IPipeline` with a null tracer and packs a `GenerationResult`."""

    def __init__(self, pipeline: IPipeline, logger: ILogger) -> None:
        self._pipeline = pipeline
        self._logger = logger

    def build(self, request: GenerationRequest) -> GenerationResult:
        tracer = NullTracer()
        state = PipelineState(
            request=request,
            config=DEFAULT_GENERATION_CONFIG,
            tracer=tracer,
        )
        self._pipeline.run(state)

        meter_result = state.last_meter_result or MeterResult(ok=False, accuracy=0.0)
        rhyme_result = state.last_rhyme_result or RhymeResult(ok=False, accuracy=0.0)

        # `iterations` counts additional feedback passes — the validation stage
        # seeds iteration 0, so len(iterations) - 1 == feedback passes performed.
        raw_iterations = tracer.iterations()
        total_iterations = max(0, len(raw_iterations) - 1)

        iteration_history = tuple(
            IterationSnapshot(
                iteration=rec.iteration,
                poem=rec.poem_text,
                meter_accuracy=rec.meter_accuracy,
                rhyme_accuracy=rec.rhyme_accuracy,
                feedback=rec.feedback,
                duration_sec=rec.duration_sec,
                raw_llm_response=rec.raw_llm_response,
                sanitized_llm_response=rec.sanitized_llm_response,
            )
            for rec in raw_iterations
        )

        validation = ValidationResult(
            meter=meter_result,
            rhyme=rhyme_result,
            iterations=total_iterations,
        )
        return GenerationResult(
            poem=state.poem,
            validation=validation,
            iteration_history=iteration_history,
        )
