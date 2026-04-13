"""Unit tests for `DefaultEvaluationAggregator`.

The aggregator is pure computation — no I/O, no logging — so these tests
exercise arithmetic, grouping, and edge cases (empty inputs, all-errors,
mixed categories) without needing the pipeline.
"""
from __future__ import annotations

import pytest

from src.domain.evaluation import AblationConfig, EvaluationSummary
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.infrastructure.evaluation.aggregator import DefaultEvaluationAggregator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_summary(
    scenario_id: str,
    config_label: str,
    *,
    meter: float,
    rhyme: float,
    iterations: int = 1,
    error: str | None = None,
) -> EvaluationSummary:
    return EvaluationSummary(
        scenario_id=scenario_id,
        scenario_name=f"name-{scenario_id}",
        config_label=config_label,
        meter="ямб",
        foot_count=4,
        rhyme_scheme="ABAB",
        meter_accuracy=meter,
        rhyme_accuracy=rhyme,
        num_iterations=iterations,
        num_lines=4,
        duration_sec=1.0,
        error=error,
    )


def _make_scenario(
    scenario_id: str,
    category: ScenarioCategory,
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


_CONFIG_A = AblationConfig(label="A", enabled_stages=frozenset(), description="baseline")
_CONFIG_B = AblationConfig(label="B", enabled_stages=frozenset(), description="with feedback")


@pytest.fixture
def aggregator() -> DefaultEvaluationAggregator:
    return DefaultEvaluationAggregator()


# ---------------------------------------------------------------------------
# Per-config aggregates
# ---------------------------------------------------------------------------

class TestConfigAggregates:
    def test_single_config_single_row_produces_same_averages(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        summaries = [_make_summary("N01", "A", meter=0.8, rhyme=0.7, iterations=1)]
        scenarios = [_make_scenario("N01", ScenarioCategory.NORMAL)]
        result = aggregator.aggregate(summaries, [_CONFIG_A], scenarios)
        assert len(result.by_config) == 1
        cfg = result.by_config[0]
        assert cfg.config_label == "A"
        assert cfg.description == "baseline"
        assert cfg.avg_meter_accuracy == pytest.approx(0.8)
        assert cfg.avg_rhyme_accuracy == pytest.approx(0.7)
        assert cfg.avg_iterations == pytest.approx(1.0)
        assert cfg.error_count == 0
        assert cfg.total_runs == 1

    def test_multiple_rows_average_correctly(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        summaries = [
            _make_summary("N01", "A", meter=0.8, rhyme=0.9, iterations=2),
            _make_summary("N02", "A", meter=0.6, rhyme=0.7, iterations=4),
        ]
        scenarios = [
            _make_scenario("N01", ScenarioCategory.NORMAL),
            _make_scenario("N02", ScenarioCategory.NORMAL),
        ]
        result = aggregator.aggregate(summaries, [_CONFIG_A], scenarios)
        cfg = result.by_config[0]
        assert cfg.avg_meter_accuracy == pytest.approx(0.7)
        assert cfg.avg_rhyme_accuracy == pytest.approx(0.8)
        assert cfg.avg_iterations == pytest.approx(3.0)
        assert cfg.total_runs == 2

    def test_error_count_reflects_failed_runs(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        summaries = [
            _make_summary("N01", "A", meter=0.8, rhyme=0.9),
            _make_summary("N02", "A", meter=0.0, rhyme=0.0, error="boom"),
            _make_summary("N03", "A", meter=0.6, rhyme=0.6, error="kaboom"),
        ]
        scenarios = [_make_scenario(s, ScenarioCategory.NORMAL) for s in ("N01", "N02", "N03")]
        result = aggregator.aggregate(summaries, [_CONFIG_A], scenarios)
        cfg = result.by_config[0]
        assert cfg.error_count == 2
        assert cfg.total_runs == 3

    def test_config_without_rows_is_skipped(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        summaries = [_make_summary("N01", "A", meter=0.8, rhyme=0.8)]
        scenarios = [_make_scenario("N01", ScenarioCategory.NORMAL)]
        # Config B has no matching rows
        result = aggregator.aggregate(summaries, [_CONFIG_A, _CONFIG_B], scenarios)
        assert len(result.by_config) == 1
        assert result.by_config[0].config_label == "A"


# ---------------------------------------------------------------------------
# Per-category aggregates
# ---------------------------------------------------------------------------

class TestCategoryAggregates:
    def test_mixed_categories_produce_separate_rows(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        summaries = [
            _make_summary("N01", "A", meter=1.0, rhyme=1.0),
            _make_summary("E01", "A", meter=0.5, rhyme=0.5),
            _make_summary("C01", "A", meter=0.0, rhyme=0.0, error="boom"),
        ]
        scenarios = [
            _make_scenario("N01", ScenarioCategory.NORMAL),
            _make_scenario("E01", ScenarioCategory.EDGE),
            _make_scenario("C01", ScenarioCategory.CORNER),
        ]
        result = aggregator.aggregate(summaries, [_CONFIG_A], scenarios)
        cats = {c.category: c for c in result.by_category}
        assert set(cats) == {"normal", "edge", "corner"}
        assert cats["normal"].avg_meter_accuracy == pytest.approx(1.0)
        assert cats["edge"].avg_meter_accuracy == pytest.approx(0.5)
        assert cats["corner"].error_count == 1

    def test_category_without_runs_is_skipped(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        summaries = [_make_summary("N01", "A", meter=1.0, rhyme=1.0)]
        scenarios = [_make_scenario("N01", ScenarioCategory.NORMAL)]
        result = aggregator.aggregate(summaries, [_CONFIG_A], scenarios)
        categories = {c.category for c in result.by_category}
        assert categories == {"normal"}  # edge/corner omitted


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_empty_summaries_returns_empty_aggregates(
        self, aggregator: DefaultEvaluationAggregator,
    ) -> None:
        result = aggregator.aggregate([], [_CONFIG_A], [])
        assert result.by_config == ()
        assert result.by_category == ()
