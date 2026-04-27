"""ValidationStage — runs meter + rhyme validators and records the result.

The stage body is deliberately thin: validators do the work, the injected
`IStageRecordBuilder` handles StageRecord serialisation, and the state is
updated. All verbose observability serialisation lives in
`DefaultStageRecordBuilder` so the control flow here stays readable.
"""
from __future__ import annotations

from src.domain.errors import DomainError
from src.domain.evaluation import IterationRecord, StageRecord
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    IFeedbackFormatter,
    ILLMCallRecorder,
    ILogger,
    IMeterValidator,
    IPipelineStage,
    IRhymeValidator,
    IStageRecordBuilder,
    IStageSkipPolicy,
    format_all_feedback,
)
from src.infrastructure.tracing.stage_timer import StageTimer


class ValidationStage(IPipelineStage):
    """Validates the initial poem against meter/rhyme constraints and seeds iteration history."""

    STAGE_NAME = "validation"

    def __init__(
        self,
        meter_validator: IMeterValidator,
        rhyme_validator: IRhymeValidator,
        feedback_formatter: IFeedbackFormatter,
        skip_policy: IStageSkipPolicy,
        logger: ILogger,
        record_builder: IStageRecordBuilder,
        llm_call_recorder: ILLMCallRecorder,
    ) -> None:
        self._meter_validator = meter_validator
        self._rhyme_validator = rhyme_validator
        self._formatter = feedback_formatter
        self._skip = skip_policy
        self._logger: ILogger = logger
        self._record_builder = record_builder
        self._llm_recorder = llm_call_recorder

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        if state.aborted:
            return

        if self._skip.should_skip(state, self.STAGE_NAME):
            state.tracer.add_stage(StageRecord(
                name=self.STAGE_NAME,
                input_summary="SKIPPED",
                output_summary="—",
            ))
            return

        with StageTimer() as t:
            try:
                m_result = self._meter_validator.validate(state.poem, state.meter)
                r_result = self._rhyme_validator.validate(state.poem, state.rhyme)
            except DomainError as exc:
                self._logger.warning("validation stage failed", error=str(exc))
                state.tracer.add_stage(StageRecord(name=self.STAGE_NAME, error=str(exc)))
                state.abort(f"validation failed: {exc}", exception=exc)
                return

        state.last_meter_result = m_result
        state.last_rhyme_result = r_result

        fb_messages = format_all_feedback(self._formatter, m_result.feedback, r_result.feedback)
        state.cached_feedback = fb_messages

        state.tracer.add_stage(
            self._record_builder.for_validation(
                poem_text=state.poem,
                meter_result=m_result,
                rhyme_result=r_result,
                duration_sec=t.elapsed,
                feedback_messages=fb_messages,
            )
        )

        snapshot = self._llm_recorder.snapshot()
        state.tracer.add_iteration(IterationRecord(
            iteration=0,
            poem_text=state.poem,
            meter_accuracy=m_result.accuracy,
            rhyme_accuracy=r_result.accuracy,
            feedback=tuple(fb_messages),
            duration_sec=t.elapsed,
            raw_llm_response=snapshot.raw,
            sanitized_llm_response=snapshot.sanitized,
            input_tokens=snapshot.input_tokens,
            output_tokens=snapshot.output_tokens,
        ))
