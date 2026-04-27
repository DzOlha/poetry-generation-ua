"""Calculator-registry composition — split out from ``metrics.py``.

Owns the metric registry, every calculator that goes into it, the
final-metrics pipeline stage, and the stage record builder. Kept apart
from the reporting sub-container so adding a metric does not touch any
reporting code (and vice versa).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import (
    IMetricCalculatorRegistry,
    IPipelineStage,
    IStageRecordBuilder,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.metrics import (
    DefaultMetricCalculatorRegistry,
    EstimatedCostCalculator,
    FeedbackIterationsCalculator,
    InputTokensCalculator,
    LineCountCalculator,
    MeterAccuracyCalculator,
    MeterImprovementCalculator,
    OutputTokensCalculator,
    RegenerationSuccessCalculator,
    RhymeAccuracyCalculator,
    RhymeImprovementCalculator,
    SemanticRelevanceCalculator,
    TotalTokensCalculator,
)
from src.infrastructure.stages import FinalMetricsStage
from src.infrastructure.stages.stage_record_builder import DefaultStageRecordBuilder

if TYPE_CHECKING:
    from src.composition_root import Container


class CalculatorRegistrySubContainer:
    """Metric registry, individual calculators, and final-metrics stage."""

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
            registry.register(InputTokensCalculator())
            registry.register(OutputTokensCalculator())
            registry.register(TotalTokensCalculator())
            cfg = self._parent.config
            registry.register(
                EstimatedCostCalculator(
                    input_price_per_m=cfg.gemini_input_price_per_m,
                    output_price_per_m=cfg.gemini_output_price_per_m,
                ),
            )
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

    def stage_record_builder(self) -> IStageRecordBuilder:
        return self._parent._get(
            CacheKey.STAGE_RECORD_BUILDER, DefaultStageRecordBuilder,
        )
