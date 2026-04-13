"""Meter accuracy metric calculator."""
from __future__ import annotations

from src.domain.ports import EvaluationContext, IMeterValidator, IMetricCalculator


class MeterAccuracyCalculator(IMetricCalculator):
    """Computes the fraction of lines that satisfy the meter constraint.

    Args:
        meter_validator: Injected IMeterValidator implementation.
    """

    def __init__(self, meter_validator: IMeterValidator) -> None:
        self._validator = meter_validator

    @property
    def name(self) -> str:
        return "meter_accuracy"

    def calculate(self, context: EvaluationContext) -> float:
        result = self._validator.validate(context.poem_text, context.meter)
        return result.accuracy
