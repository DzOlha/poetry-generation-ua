"""SequentialPipeline — IPipeline implementation walking stages in order.

The final-metrics stage is optional: `EvaluationService` passes one so the
trace carries quality numbers; `PoetryService.generate` does not (it only
needs the final poem + validation result, and recomputing metrics would
duplicate work the validation stage already did).
"""
from __future__ import annotations

from src.domain.pipeline_context import PipelineState
from src.domain.ports import IPipeline, IPipelineStage


class SequentialPipeline(IPipeline):
    """Runs each pipeline stage sequentially, then an optional final metrics stage."""

    def __init__(
        self,
        stages: list[IPipelineStage],
        final_metrics_stage: IPipelineStage | None = None,
    ) -> None:
        self._stages = list(stages)
        self._final_metrics_stage = final_metrics_stage

    def run(self, state: PipelineState) -> None:
        for stage in self._stages:
            stage.run(state)
        # Final metrics always run (if configured), even after an abort, so
        # the trace still carries the partial state.
        if self._final_metrics_stage is not None:
            self._final_metrics_stage.run(state)
