"""Contract tests wiring each IMetricCalculator through IMetricCalculatorContract."""
from __future__ import annotations

from src.domain.ports import IMetricCalculator
from src.infrastructure.metrics import (
    FeedbackIterationsCalculator,
    LineCountCalculator,
    MeterImprovementCalculator,
    RegenerationSuccessCalculator,
    RhymeImprovementCalculator,
)
from tests.contracts.metric_calculator_contract import IMetricCalculatorContract


class TestLineCountCalculatorContract(IMetricCalculatorContract):
    def _make_calculator(self) -> IMetricCalculator:
        return LineCountCalculator()


class TestRegenerationSuccessCalculatorContract(IMetricCalculatorContract):
    def _make_calculator(self) -> IMetricCalculator:
        return RegenerationSuccessCalculator()


class TestMeterImprovementCalculatorContract(IMetricCalculatorContract):
    def _make_calculator(self) -> IMetricCalculator:
        return MeterImprovementCalculator()


class TestRhymeImprovementCalculatorContract(IMetricCalculatorContract):
    def _make_calculator(self) -> IMetricCalculator:
        return RhymeImprovementCalculator()


class TestFeedbackIterationsCalculatorContract(IMetricCalculatorContract):
    def _make_calculator(self) -> IMetricCalculator:
        return FeedbackIterationsCalculator()
