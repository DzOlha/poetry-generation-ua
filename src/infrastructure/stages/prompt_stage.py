"""PromptStage — builds the LLM prompt from request + retrieved context."""
from __future__ import annotations

from src.domain.evaluation import StageRecord
from src.domain.pipeline_context import PipelineState
from src.domain.ports import IPipelineStage, IPromptBuilder
from src.infrastructure.tracing.stage_timer import StageTimer


class PromptStage(IPipelineStage):
    """Invokes IPromptBuilder and stores the resulting prompt on the state."""

    STAGE_NAME = "prompt_construction"

    def __init__(self, prompt_builder: IPromptBuilder) -> None:
        self._prompt_builder = prompt_builder

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        if state.aborted:
            return

        with StageTimer() as t:
            state.prompt = self._prompt_builder.build(
                state.request,
                state.retrieved,
                state.metric_examples,
            )

        meter = state.meter
        rhyme = state.rhyme
        state.tracer.add_stage(StageRecord(
            name=self.STAGE_NAME,
            input_summary=(
                f"theme={state.theme!r}, meter={meter.name}, "
                f"scheme={rhyme.pattern}"
            ),
            output_summary=f"prompt length={len(state.prompt)} chars",
            output_data=state.prompt,
            metrics={
                "prompt_length": len(state.prompt),
                "num_metric_examples": len(state.metric_examples),
            },
            duration_sec=t.elapsed,
        ))
