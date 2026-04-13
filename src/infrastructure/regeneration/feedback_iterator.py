"""Default IFeedbackIterator: regenerate → merge → re-validate up to N times.

The iterator orchestrates the feedback loop but owns none of its
sub-concerns. Validation + formatting live behind `IFeedbackCycle`,
poem merging behind `IRegenerationMerger`, stop conditions behind
`IIterationStopPolicy`, and LLM calls behind `ILLMProvider`.

This is the single source of truth for the feedback-loop algorithm;
`PoetryService.generate` used to run a subtly different copy, which meant
evaluation scored un-merged poems while handlers saw merged output.
"""
from __future__ import annotations

from src.domain.errors import DomainError
from src.domain.evaluation import IterationRecord, StageRecord
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    IFeedbackCycle,
    IFeedbackIterator,
    IIterationStopPolicy,
    ILLMProvider,
    ILogger,
    IRegenerationMerger,
)
from src.infrastructure.tracing.stage_timer import StageTimer


class ValidatingFeedbackIterator(IFeedbackIterator):
    """Regenerate → merge → re-validate, gated by an IIterationStopPolicy."""

    def __init__(
        self,
        llm: ILLMProvider,
        feedback_cycle: IFeedbackCycle,
        regeneration_merger: IRegenerationMerger,
        stop_policy: IIterationStopPolicy,
        logger: ILogger,
    ) -> None:
        self._llm = llm
        self._cycle = feedback_cycle
        self._merger = regeneration_merger
        self._stop = stop_policy
        self._logger = logger

    def iterate(self, state: PipelineState) -> None:
        m_result = state.last_meter_result
        r_result = state.last_rhyme_result
        if m_result is None or r_result is None:
            return  # Validation stage was skipped — nothing to refine.

        # The validation stage already formatted the initial feedback; reuse
        # it for the first LLM call instead of re-running the formatter.
        cached = state.cached_feedback
        feedback_messages: tuple[str, ...] = (
            tuple(cached) if cached is not None else ()
        )

        for it in range(1, state.max_iterations + 1):
            if self._stop.should_stop(
                it, state.max_iterations, m_result, r_result, state.tracer.iterations(),
            ):
                break
            with StageTimer() as t_iter:
                try:
                    prev_poem = state.poem
                    regenerated = self._llm.regenerate_lines(
                        state.poem, list(feedback_messages),
                    )
                    state.poem = self._merger.merge(
                        prev_poem,
                        regenerated,
                        m_result.feedback,
                        r_result.feedback,
                    )
                    outcome = self._cycle.run(
                        state.poem, state.meter, state.rhyme,
                    )
                    m_result = outcome.meter
                    r_result = outcome.rhyme
                    feedback_messages = outcome.feedback_messages
                except DomainError as exc:
                    self._logger.error(
                        "feedback iteration failed",
                        iter=it,
                        error=str(exc),
                    )
                    state.tracer.add_stage(StageRecord(
                        name=f"feedback_iter_{it}",
                        error=str(exc),
                    ))
                    break

            state.tracer.add_iteration(IterationRecord(
                iteration=it,
                poem_text=state.poem,
                meter_accuracy=m_result.accuracy,
                rhyme_accuracy=r_result.accuracy,
                feedback=feedback_messages,
                duration_sec=t_iter.elapsed,
            ))

        state.last_meter_result = m_result
        state.last_rhyme_result = r_result
