"""Contract every `IMetricCalculator` implementation must satisfy."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from src.domain.models import MeterSpec, RhymeScheme
from src.domain.ports import EvaluationContext, IMetricCalculator


class IMetricCalculatorContract(ABC):
    """Every IMetricCalculator must satisfy these behavioural guarantees."""

    @abstractmethod
    def _make_calculator(self) -> IMetricCalculator:
        """Return a fresh calculator under test."""

    @staticmethod
    def _basic_context() -> EvaluationContext:
        return EvaluationContext(
            poem_text=(
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
            iterations=[],
            theme="весна",
        )

    def test_has_non_empty_name(self) -> None:
        calc = self._make_calculator()
        assert isinstance(calc.name, str)
        assert calc.name, "IMetricCalculator.name must be a non-empty string"

    def test_returns_finite_float(self) -> None:
        calc = self._make_calculator()
        value = calc.calculate(self._basic_context())
        assert isinstance(value, int | float)
        assert math.isfinite(float(value))

    def test_does_not_mutate_context(self) -> None:
        calc = self._make_calculator()
        ctx = self._basic_context()
        before = (ctx.poem_text, ctx.meter, ctx.rhyme, ctx.theme, list(ctx.iterations))
        calc.calculate(ctx)
        after = (ctx.poem_text, ctx.meter, ctx.rhyme, ctx.theme, list(ctx.iterations))
        assert before == after, "calculate() must not mutate the EvaluationContext"

    def test_empty_iterations_accepted(self) -> None:
        calc = self._make_calculator()
        ctx = EvaluationContext(
            poem_text="рядок\nрядок\nрядок\nрядок\n",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
            iterations=[],
            theme="",
        )
        value = calc.calculate(ctx)
        assert math.isfinite(float(value))
