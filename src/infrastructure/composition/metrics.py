"""Metrics sub-container.

Owns metric calculators + registry, final-metrics stage, reporter,
results writer, tracer factory, HTTP error mapper, stage record builder,
and the evaluation aggregator. Everything that is purely observational
or post-run reporting lives here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import (
    IEvaluationAggregator,
    IHttpErrorMapper,
    IMetricCalculatorRegistry,
    IPipelineStage,
    IReporter,
    IResultsWriter,
    IStageRecordBuilder,
    ITracerFactory,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.evaluation import DefaultEvaluationAggregator
from src.infrastructure.http import DefaultHttpErrorMapper
from src.infrastructure.metrics import (
    DefaultMetricCalculatorRegistry,
    FeedbackIterationsCalculator,
    LineCountCalculator,
    MeterAccuracyCalculator,
    MeterImprovementCalculator,
    RegenerationSuccessCalculator,
    RhymeAccuracyCalculator,
    RhymeImprovementCalculator,
    SemanticRelevanceCalculator,
)
from src.infrastructure.reporting import JsonResultsWriter, MarkdownReporter
from src.infrastructure.stages import FinalMetricsStage
from src.infrastructure.stages.stage_record_builder import DefaultStageRecordBuilder
from src.infrastructure.tracing import PipelineTracerFactory

if TYPE_CHECKING:
    from src.composition_root import Container


class MetricsSubContainer:
    """Metric calculators, reporters, and tracing factories."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def metric_registry(self) -> IMetricCalculatorRegistry:
        def factory() -> IMetricCalculatorRegistry:
            registry = DefaultMetricCalculatorRegistry()
            val = self._parent.validation
            registry.register(
                MeterAccuracyCalculator(meter_validator=val.meter_validator()),
            )
            registry.register(
                RhymeAccuracyCalculator(rhyme_validator=val.rhyme_validator()),
            )
            registry.register(RegenerationSuccessCalculator())
            registry.register(
                SemanticRelevanceCalculator(
                    embedder=self._parent.generation.embedder(),
                    logger=self._parent.logger,
                ),
            )
            registry.register(LineCountCalculator())
            registry.register(MeterImprovementCalculator())
            registry.register(RhymeImprovementCalculator())
            registry.register(FeedbackIterationsCalculator())
            return registry

        return self._parent._get(CacheKey.METRIC_REGISTRY, factory)

    def final_metrics_stage(self) -> IPipelineStage:
        return self._parent._get(
            CacheKey.FINAL_METRICS_STAGE,
            lambda: FinalMetricsStage(
                registry=self.metric_registry(),
                logger=self._parent.logger,
            ),
        )

    def reporter(self) -> IReporter:
        def factory() -> IReporter:
            from src.domain.evaluation import ABLATION_CONFIGS

            cfg = self._parent.config
            provider = cfg.llm_provider or ("gemini" if cfg.gemini_api_key else "mock")
            model = cfg.gemini_model if provider == "gemini" else None
            descriptions = {c.label: c.description for c in ABLATION_CONFIGS if c.description}
            return MarkdownReporter(
                llm_provider=provider,
                llm_model=model,
                config_descriptions=descriptions,
            )

        return self._parent._get(CacheKey.REPORTER, factory)

    def results_writer(self) -> IResultsWriter:
        return self._parent._get(
            CacheKey.RESULTS_WRITER,
            lambda: JsonResultsWriter(reporter=self.reporter()),
        )

    def tracer_factory(self) -> ITracerFactory:
        return self._parent._get(CacheKey.TRACER_FACTORY, PipelineTracerFactory)

    def http_error_mapper(self) -> IHttpErrorMapper:
        return self._parent._get(CacheKey.HTTP_ERROR_MAPPER, DefaultHttpErrorMapper)

    def stage_record_builder(self) -> IStageRecordBuilder:
        return self._parent._get(
            CacheKey.STAGE_RECORD_BUILDER, DefaultStageRecordBuilder,
        )

    def evaluation_aggregator(self) -> IEvaluationAggregator:
        return self._parent._get(
            CacheKey.EVALUATION_AGGREGATOR, DefaultEvaluationAggregator,
        )
