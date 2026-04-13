"""Regeneration success metric calculator."""
from __future__ import annotations

from src.domain.ports import EvaluationContext, IMetricCalculator


class RegenerationSuccessCalculator(IMetricCalculator):
    """Measures the quality improvement achieved through the feedback loop.

    Returns the raw delta of average (meter + rhyme) accuracy between the
    first and last iteration. Negative values are returned as-is to expose
    LLM degradation — consumers can clamp or display as they wish.
    """

    @property
    def name(self) -> str:
        return "regeneration_success"

    def calculate(self, context: EvaluationContext) -> float:
        if len(context.iterations) < 2:
            return 0.0

        initial = context.iterations[0]
        final = context.iterations[-1]

        meter_improvement = final.meter_accuracy - initial.meter_accuracy
        rhyme_improvement = final.rhyme_accuracy - initial.rhyme_accuracy
        return (meter_improvement + rhyme_improvement) / 2.0
