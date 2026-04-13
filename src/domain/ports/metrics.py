"""Metric calculation ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.domain.models import MeterSpec, RhymeScheme

if TYPE_CHECKING:
    from src.domain.evaluation import IterationRecord


@dataclass(frozen=True)
class EvaluationContext:
    """Input bundle for metric calculators."""

    poem_text: str
    meter: MeterSpec
    rhyme: RhymeScheme
    iterations: list[IterationRecord] = field(default_factory=list)
    theme: str = ""


class IMetricCalculator(ABC):
    """Computes a single scalar quality metric for a generated poem."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def calculate(self, context: EvaluationContext) -> float: ...


class IMetricCalculatorRegistry(ABC):
    """Registry of available metric calculators."""

    @abstractmethod
    def register(self, calculator: IMetricCalculator) -> None: ...

    @abstractmethod
    def all(self) -> tuple[IMetricCalculator, ...]: ...
