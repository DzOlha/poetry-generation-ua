"""Regeneration success metric calculator."""
from __future__ import annotations

from src.domain.ports import EvaluationContext, IMetricCalculator


class RegenerationSuccessCalculator(IMetricCalculator):
    """Violation-coverage ratio between the first and last iteration.

    Defines violations as (1 − meter_accuracy) + (1 − rhyme_accuracy) and
    returns ``1 − final_violations / initial_violations``. The resulting
    number answers "what fraction of the initial violation budget did the
    feedback loop resolve?": 1.0 = every violation fixed, 0.0 = none
    fixed, negative = regeneration made things worse. When the initial
    poem already had zero violations there is nothing to repair and the
    metric is 1.0 (vacuously successful).

    Preferred over a raw accuracy delta because a metric that was already
    at the ceiling (e.g. rhyme=100%) cannot contribute to improvement and
    unfairly drags the average down.
    """

    @property
    def name(self) -> str:
        return "regeneration_success"

    def calculate(self, context: EvaluationContext) -> float:
        if len(context.iterations) < 2:
            return 0.0

        initial = context.iterations[0]
        final = context.iterations[-1]

        initial_violations = (1.0 - initial.meter_accuracy) + (1.0 - initial.rhyme_accuracy)
        final_violations = (1.0 - final.meter_accuracy) + (1.0 - final.rhyme_accuracy)

        if initial_violations <= 0.0:
            return 1.0
        return 1.0 - final_violations / initial_violations
