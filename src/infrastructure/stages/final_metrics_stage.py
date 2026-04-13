"""FinalMetricsStage — runs every registered IMetricCalculator and stores results.

All "final metrics" are now `IMetricCalculator` implementations — nothing
is computed inline. Adding a new metric becomes a registration call on the
injected `IMetricCalculatorRegistry`.
"""
from __future__ import annotations

from src.domain.evaluation import MetricValue
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    EvaluationContext,
    ILogger,
    IMetricCalculatorRegistry,
    IPipelineStage,
)


class FinalMetricsStage(IPipelineStage):
    """Populates PipelineTrace.final_metrics from the metric calculator registry."""

    STAGE_NAME = "final_metrics"

    def __init__(
        self,
        registry: IMetricCalculatorRegistry,
        logger: ILogger,
    ) -> None:
        self._registry = registry
        self._logger: ILogger = logger

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        state.tracer.set_final_poem(state.poem)

        if state.aborted:
            state.tracer.set_error(state.abort_reason)
            return

        iterations = state.tracer.iterations()
        context = EvaluationContext(
            poem_text=state.poem,
            meter=state.meter,
            rhyme=state.rhyme,
            iterations=list(iterations),
            theme=state.theme,
        )

        metrics: dict[str, MetricValue] = {}
        for calc in self._registry.all():
            try:
                metrics[calc.name] = calc.calculate(context)
            except Exception as exc:  # noqa: BLE001 — metrics must never crash the run
                self._logger.warning(
                    "metric calculator failed",
                    name=calc.name,
                    error=str(exc),
                )
                metrics[calc.name] = 0.0

        state.tracer.set_final_metrics(metrics)
        state.final_metrics = metrics
