"""Evaluation and scenario registry ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.evaluation import AblationConfig, EvaluationSummary, StageRecord
    from src.domain.models import MeterResult, RhymeResult
    from src.domain.scenarios import EvaluationScenario
    from src.domain.values import ScenarioCategory


class IScenarioRegistry(ABC):
    """Immutable registry of evaluation scenarios."""

    @property
    @abstractmethod
    def all(self) -> tuple[EvaluationScenario, ...]: ...

    @abstractmethod
    def by_id(self, scenario_id: str) -> EvaluationScenario | None: ...

    @abstractmethod
    def by_category(
        self, category: ScenarioCategory,
    ) -> tuple[EvaluationScenario, ...]: ...


@dataclass(frozen=True)
class ConfigAggregate:
    """Average metrics + error count for one ablation config across scenarios."""

    config_label: str
    description: str
    avg_meter_accuracy: float
    avg_rhyme_accuracy: float
    avg_iterations: float
    error_count: int
    total_runs: int


@dataclass(frozen=True)
class CategoryAggregate:
    """Average metrics + error count for one scenario category."""

    category: str
    total_runs: int
    avg_meter_accuracy: float
    avg_rhyme_accuracy: float
    error_count: int


@dataclass(frozen=True)
class EvaluationAggregates:
    """All aggregate statistics computed from a matrix run."""

    by_config: tuple[ConfigAggregate, ...]
    by_category: tuple[CategoryAggregate, ...]


class IEvaluationAggregator(ABC):
    """Computes aggregate statistics from a list of EvaluationSummary rows."""

    @abstractmethod
    def aggregate(
        self,
        summaries: list[EvaluationSummary],
        configs: Iterable[AblationConfig],
        scenarios: Iterable[EvaluationScenario],
    ) -> EvaluationAggregates: ...


class IStageRecordBuilder(ABC):
    """Builds `StageRecord` observability payloads for pipeline stages."""

    @abstractmethod
    def for_validation(
        self,
        poem_text: str,
        meter_result: MeterResult,
        rhyme_result: RhymeResult,
        duration_sec: float,
        *,
        feedback_messages: list[str] | None = None,
    ) -> StageRecord: ...
