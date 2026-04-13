"""Unit tests for `StaticScenarioRegistry`.

Verifies the adapter presents the `IScenarioRegistry` contract over a
fixed tuple of scenarios, and can be constructed with either the default
`ALL_SCENARIOS` set or a caller-provided iterable for tests.
"""
from __future__ import annotations

import pytest

from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.infrastructure.evaluation.scenario_data import ALL_SCENARIOS
from src.infrastructure.evaluation.scenario_registry import StaticScenarioRegistry


def _make_scenario(
    scenario_id: str, category: ScenarioCategory = ScenarioCategory.NORMAL,
) -> EvaluationScenario:
    return EvaluationScenario(
        id=scenario_id,
        name=f"name-{scenario_id}",
        category=category,
        theme="тест",
        meter="ямб",
        foot_count=4,
        rhyme_scheme="ABAB",
    )


class TestDefaultRegistry:
    def test_uses_all_scenarios_when_no_argument_passed(self) -> None:
        registry = StaticScenarioRegistry()
        assert registry.all == ALL_SCENARIOS

    def test_by_id_returns_known_scenario(self) -> None:
        registry = StaticScenarioRegistry()
        scenario = registry.by_id("N01")
        assert scenario is not None
        assert scenario.id == "N01"

    def test_by_id_returns_none_for_unknown(self) -> None:
        registry = StaticScenarioRegistry()
        assert registry.by_id("ZZZ") is None


class TestCustomRegistry:
    def test_accepts_caller_provided_scenarios(self) -> None:
        scenarios = (_make_scenario("X01"), _make_scenario("X02"))
        registry = StaticScenarioRegistry(scenarios)
        assert registry.all == scenarios

    def test_by_category_filters_correctly(self) -> None:
        scenarios = (
            _make_scenario("N01", ScenarioCategory.NORMAL),
            _make_scenario("E01", ScenarioCategory.EDGE),
            _make_scenario("C01", ScenarioCategory.CORNER),
            _make_scenario("N02", ScenarioCategory.NORMAL),
        )
        registry = StaticScenarioRegistry(scenarios)
        normal = registry.by_category(ScenarioCategory.NORMAL)
        edge = registry.by_category(ScenarioCategory.EDGE)
        assert {s.id for s in normal} == {"N01", "N02"}
        assert {s.id for s in edge} == {"E01"}

    def test_duplicate_ids_raise(self) -> None:
        # The underlying ScenarioRegistry enforces uniqueness — verify
        # StaticScenarioRegistry propagates the failure.
        scenarios = (_make_scenario("X01"), _make_scenario("X01"))
        with pytest.raises(Exception):  # UnsupportedConfigError
            StaticScenarioRegistry(scenarios)
