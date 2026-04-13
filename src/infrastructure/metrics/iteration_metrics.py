"""Iteration-delta metrics — meter improvement, rhyme improvement, feedback_iterations.

Each used to be computed inline inside `FinalMetricsStage`; moving them
into the registry means adding or tuning another metric no longer requires
touching the stage.
"""
from __future__ import annotations

from src.domain.ports import EvaluationContext, IMetricCalculator


class _IterationDeltaCalculator(IMetricCalculator):
    """Base class for metrics that compare first vs last iteration accuracy."""

    def __init__(self, metric_name: str, field: str) -> None:
        self._name = metric_name
        self._field = field

    @property
    def name(self) -> str:
        return self._name

    def calculate(self, context: EvaluationContext) -> float:
        iterations = context.iterations
        if len(iterations) < 2:
            return 0.0
        initial = getattr(iterations[0], self._field)
        final = getattr(iterations[-1], self._field)
        return float(final - initial)


class MeterImprovementCalculator(_IterationDeltaCalculator):
    """Final − initial meter accuracy across feedback iterations."""

    def __init__(self) -> None:
        super().__init__("meter_improvement", "meter_accuracy")


class RhymeImprovementCalculator(_IterationDeltaCalculator):
    """Final − initial rhyme accuracy across feedback iterations."""

    def __init__(self) -> None:
        super().__init__("rhyme_improvement", "rhyme_accuracy")


class FeedbackIterationsCalculator(IMetricCalculator):
    """Number of feedback iterations performed (excludes the initial validation)."""

    @property
    def name(self) -> str:
        return "feedback_iterations"

    def calculate(self, context: EvaluationContext) -> float:
        n = len(context.iterations)
        return float(max(0, n - 1))
