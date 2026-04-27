"""Metrics sub-container — façade composing two focused sub-containers.

The original module bundled two unrelated concerns: the metric
calculator registry (one responsibility) and the post-run reporting
graph (another). After the audit they live in their own modules:

  - ``metrics_calculator_registry`` — registry + calculators + final stage
  - ``metrics_reporting``           — reporter, writers, tracer factory,
                                      HTTP error mapper, aggregator

This file preserves the public ``MetricsSubContainer`` API so the
parent ``Container`` and existing call sites don't need to change.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import (
    IBatchResultsWriter,
    IEvaluationAggregator,
    IHttpErrorMapper,
    IMetricCalculatorRegistry,
    IPipelineStage,
    IReporter,
    IResultsWriter,
    IStageRecordBuilder,
    ITracerFactory,
)
from src.infrastructure.composition.metrics_calculator_registry import (
    CalculatorRegistrySubContainer,
)
from src.infrastructure.composition.metrics_reporting import ReportingSubContainer

if TYPE_CHECKING:
    from src.composition_root import Container


class MetricsSubContainer:
    """Thin façade — calculator registry + reporting over the shared cache."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent
        self._calculators = CalculatorRegistrySubContainer(parent)
        self._reporting = ReportingSubContainer(parent)

    # ------------------------------------------------------------------
    # Calculator-registry delegation
    # ------------------------------------------------------------------

    def metric_registry(self) -> IMetricCalculatorRegistry:
        return self._calculators.metric_registry()

    def final_metrics_stage(self) -> IPipelineStage:
        return self._calculators.final_metrics_stage()

    def stage_record_builder(self) -> IStageRecordBuilder:
        return self._calculators.stage_record_builder()

    # ------------------------------------------------------------------
    # Reporting delegation
    # ------------------------------------------------------------------

    def reporter(self) -> IReporter:
        return self._reporting.reporter()

    def results_writer(self) -> IResultsWriter:
        return self._reporting.results_writer()

    def batch_results_writer(self) -> IBatchResultsWriter:
        return self._reporting.batch_results_writer()

    def tracer_factory(self) -> ITracerFactory:
        return self._reporting.tracer_factory()

    def http_error_mapper(self) -> IHttpErrorMapper:
        return self._reporting.http_error_mapper()

    def evaluation_aggregator(self) -> IEvaluationAggregator:
        return self._reporting.evaluation_aggregator()
