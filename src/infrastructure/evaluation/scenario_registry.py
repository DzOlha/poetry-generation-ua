"""`IScenarioRegistry` implementation backed by `ALL_SCENARIOS`.

Wraps the domain-layer `ScenarioRegistry` so consumers depend on the
abstract port instead of importing `SCENARIO_REGISTRY` from
`src.domain.scenarios` directly. Alternative implementations can serve
subsets (e.g. a test registry with only normal scenarios) without
touching callers.
"""
from __future__ import annotations

from collections.abc import Iterable

from src.domain.ports import IScenarioRegistry
from src.domain.scenarios import EvaluationScenario, ScenarioRegistry
from src.domain.values import ScenarioCategory
from src.infrastructure.evaluation.scenario_data import ALL_SCENARIOS


class StaticScenarioRegistry(IScenarioRegistry):
    """`IScenarioRegistry` backed by a fixed tuple of scenarios.

    Default argument uses `ALL_SCENARIOS` so production code gets the full
    matrix; tests can pass a custom iterable to exercise subsets without
    monkey-patching the domain module.
    """

    def __init__(
        self,
        scenarios: Iterable[EvaluationScenario] | None = None,
    ) -> None:
        items = tuple(scenarios) if scenarios is not None else ALL_SCENARIOS
        self._registry = ScenarioRegistry(items)

    @property
    def all(self) -> tuple[EvaluationScenario, ...]:
        return self._registry.all

    def by_id(self, scenario_id: str) -> EvaluationScenario | None:
        return self._registry.by_id(scenario_id)

    def by_category(
        self, category: ScenarioCategory,
    ) -> tuple[EvaluationScenario, ...]:
        return self._registry.by_category(category)
