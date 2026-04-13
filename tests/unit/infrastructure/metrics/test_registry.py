"""Tests for DefaultMetricCalculatorRegistry."""
from __future__ import annotations

import pytest

from src.domain.errors import ConfigurationError
from src.domain.ports import EvaluationContext, IMetricCalculator
from src.infrastructure.metrics import DefaultMetricCalculatorRegistry


class _StubCalculator(IMetricCalculator):
    def __init__(self, name: str, value: float = 0.5) -> None:
        self._name = name
        self._value = value

    @property
    def name(self) -> str:
        return self._name

    def calculate(self, context: EvaluationContext) -> float:
        return self._value


class TestDefaultMetricCalculatorRegistry:
    def test_empty_registry_returns_empty_tuple(self):
        assert DefaultMetricCalculatorRegistry().all() == ()

    def test_register_preserves_order(self):
        registry = DefaultMetricCalculatorRegistry()
        registry.register(_StubCalculator("first"))
        registry.register(_StubCalculator("second"))
        registry.register(_StubCalculator("third"))
        names = [c.name for c in registry.all()]
        assert names == ["first", "second", "third"]

    def test_register_rejects_duplicate_names(self):
        registry = DefaultMetricCalculatorRegistry()
        registry.register(_StubCalculator("dup"))
        with pytest.raises(ConfigurationError, match="Duplicate metric calculator"):
            registry.register(_StubCalculator("dup"))

    def test_all_returns_tuple_snapshot(self):
        registry = DefaultMetricCalculatorRegistry()
        registry.register(_StubCalculator("one"))
        snap1 = registry.all()
        registry.register(_StubCalculator("two"))
        snap2 = registry.all()
        assert len(snap1) == 1
        assert len(snap2) == 2
