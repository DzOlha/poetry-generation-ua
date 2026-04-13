"""Rhyme accuracy metric calculator."""
from __future__ import annotations

from src.domain.ports import EvaluationContext, IMetricCalculator, IRhymeValidator


class RhymeAccuracyCalculator(IMetricCalculator):
    """Computes the fraction of rhyme pairs that pass phonetic similarity check.

    Args:
        rhyme_validator: Injected IRhymeValidator implementation.
    """

    def __init__(self, rhyme_validator: IRhymeValidator) -> None:
        self._validator = rhyme_validator

    @property
    def name(self) -> str:
        return "rhyme_accuracy"

    def calculate(self, context: EvaluationContext) -> float:
        result = self._validator.validate(context.poem_text, context.rhyme)
        return result.accuracy
