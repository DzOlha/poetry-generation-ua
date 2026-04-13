"""MetricExamplesStage — fetches verified metric reference poems for the prompt."""
from __future__ import annotations

from src.domain.errors import DomainError
from src.domain.evaluation import StageRecord
from src.domain.models import MetricQuery
from src.domain.pipeline_context import PipelineState
from src.domain.ports import ILogger, IMetricRepository, IPipelineStage, IStageSkipPolicy
from src.infrastructure.tracing.stage_timer import StageTimer


class MetricExamplesStage(IPipelineStage):
    """Loads verified metric examples matching the request's meter/scheme."""

    STAGE_NAME = "metric_examples"

    def __init__(
        self,
        metric_repo: IMetricRepository,
        skip_policy: IStageSkipPolicy,
        logger: ILogger,
    ) -> None:
        self._metric_repo = metric_repo
        self._skip = skip_policy
        self._logger: ILogger = logger

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        if state.aborted:
            return

        if self._skip.should_skip(state, self.STAGE_NAME):
            state.tracer.add_stage(StageRecord(
                name=self.STAGE_NAME,
                input_summary="SKIPPED (config.metric_examples disabled)",
                output_summary="—",
                metrics={"num_examples": 0},
            ))
            return

        meter = state.meter
        rhyme = state.rhyme
        with StageTimer() as t:
            try:
                state.metric_examples = self._metric_repo.find(MetricQuery(
                    meter=meter.name,
                    feet=meter.foot_count,
                    scheme=rhyme.pattern,
                    top_k=state.metric_examples_top_k,
                ))
            except DomainError as exc:
                self._logger.warning("metric_examples stage failed", error=str(exc))
                state.tracer.add_stage(StageRecord(
                    name=self.STAGE_NAME,
                    input_summary=f"meter={meter.name}, feet={meter.foot_count}",
                    error=str(exc),
                ))
                state.metric_examples = []
                return

        examples = state.metric_examples
        state.tracer.add_stage(StageRecord(
            name=self.STAGE_NAME,
            input_summary=(
                f"meter={meter.name}, feet={meter.foot_count}, "
                f"scheme={rhyme.pattern}"
            ),
            output_summary=f"found {len(examples)} metric examples",
            output_data=[
                {
                    "id": e.id, "meter": e.meter, "feet": e.feet,
                    "scheme": e.scheme, "verified": e.verified, "text": e.text,
                }
                for e in examples
            ],
            metrics={"num_examples": len(examples)},
            duration_sec=t.elapsed,
        ))
