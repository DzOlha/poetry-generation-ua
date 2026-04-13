"""FeedbackLoopStage — thin facade delegating to IFeedbackIterator."""
from __future__ import annotations

from src.domain.evaluation import StageRecord
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    IFeedbackIterator,
    IPipelineStage,
    IStageSkipPolicy,
)


class FeedbackLoopStage(IPipelineStage):
    """Runs the feedback iterator and writes a closing StageRecord."""

    STAGE_NAME = "feedback_loop"

    def __init__(
        self,
        iterator: IFeedbackIterator,
        skip_policy: IStageSkipPolicy,
    ) -> None:
        self._iterator = iterator
        self._skip = skip_policy

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        if self._skip.should_skip(state, self.STAGE_NAME):
            state.tracer.add_stage(StageRecord(
                name=self.STAGE_NAME,
                input_summary="SKIPPED",
                output_summary="—",
            ))
            return

        if state.last_meter_result is None or state.last_rhyme_result is None:
            # Validation stage was skipped — nothing to refine.
            state.tracer.add_stage(StageRecord(
                name=self.STAGE_NAME,
                input_summary="SKIPPED (no initial validation)",
                output_summary="—",
            ))
            return

        self._iterator.iterate(state)

        m_result = state.last_meter_result
        r_result = state.last_rhyme_result
        iter_count = len(state.tracer.iterations())

        state.tracer.add_stage(StageRecord(
            name=self.STAGE_NAME,
            input_summary=f"max_iterations={state.max_iterations}",
            output_summary=(
                f"{iter_count} iterations, "
                f"final meter={m_result.accuracy:.2%} rhyme={r_result.accuracy:.2%}"
            ),
            metrics={
                "total_iterations": iter_count,
                "final_meter_accuracy": m_result.accuracy,
                "final_rhyme_accuracy": r_result.accuracy,
            },
        ))
