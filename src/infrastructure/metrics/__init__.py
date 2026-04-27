"""Metric calculator implementations.

Each class implements IMetricCalculator and computes a single quality
dimension of a generated poem. Inject a list of calculators into
`FinalMetricsStage` via `IMetricCalculatorRegistry` to extend the
final_metrics dict without changing the stage itself.
"""
from src.infrastructure.metrics.iteration_metrics import (
    FeedbackIterationsCalculator,
    MeterImprovementCalculator,
    RhymeImprovementCalculator,
)
from src.infrastructure.metrics.line_count import LineCountCalculator
from src.infrastructure.metrics.meter_accuracy import MeterAccuracyCalculator
from src.infrastructure.metrics.regeneration_success import RegenerationSuccessCalculator
from src.infrastructure.metrics.registry import DefaultMetricCalculatorRegistry
from src.infrastructure.metrics.rhyme_accuracy import RhymeAccuracyCalculator
from src.infrastructure.metrics.semantic_relevance import SemanticRelevanceCalculator
from src.infrastructure.metrics.token_usage import (
    EstimatedCostCalculator,
    InputTokensCalculator,
    OutputTokensCalculator,
    TotalTokensCalculator,
)

__all__ = [
    "DefaultMetricCalculatorRegistry",
    "EstimatedCostCalculator",
    "FeedbackIterationsCalculator",
    "InputTokensCalculator",
    "LineCountCalculator",
    "MeterAccuracyCalculator",
    "MeterImprovementCalculator",
    "OutputTokensCalculator",
    "RegenerationSuccessCalculator",
    "RhymeAccuracyCalculator",
    "RhymeImprovementCalculator",
    "SemanticRelevanceCalculator",
    "TotalTokensCalculator",
]
