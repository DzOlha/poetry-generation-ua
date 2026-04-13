"""Default metric calculator registry."""
from __future__ import annotations

from src.domain.errors import ConfigurationError
from src.domain.ports import IMetricCalculator, IMetricCalculatorRegistry


class DefaultMetricCalculatorRegistry(IMetricCalculatorRegistry):
    """In-memory registry that preserves registration order and rejects duplicates."""

    def __init__(self) -> None:
        self._calculators: list[IMetricCalculator] = []
        self._names: set[str] = set()

    def register(self, calculator: IMetricCalculator) -> None:
        if calculator.name in self._names:
            raise ConfigurationError(
                f"Duplicate metric calculator: {calculator.name!r}",
            )
        self._names.add(calculator.name)
        self._calculators.append(calculator)

    def all(self) -> tuple[IMetricCalculator, ...]:
        return tuple(self._calculators)
