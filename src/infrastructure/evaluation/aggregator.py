"""`IEvaluationAggregator` implementation — pure computation, zero I/O.

Extracted from `EvaluationRunner._emit_aggregates` so stats computation
is independently unit-testable. The runner now orchestrates only; this
class does the arithmetic and returns structured value objects.
"""
from __future__ import annotations

from collections.abc import Iterable

from src.domain.evaluation import AblationConfig, EvaluationSummary
from src.domain.ports import (
    CategoryAggregate,
    ConfigAggregate,
    EvaluationAggregates,
    IEvaluationAggregator,
)
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory


class DefaultEvaluationAggregator(IEvaluationAggregator):
    """Computes per-config and per-category aggregates from a matrix run."""

    def aggregate(
        self,
        summaries: list[EvaluationSummary],
        configs: Iterable[AblationConfig],
        scenarios: Iterable[EvaluationScenario],
    ) -> EvaluationAggregates:
        return EvaluationAggregates(
            by_config=self._aggregate_by_config(summaries, configs),
            by_category=self._aggregate_by_category(summaries, scenarios),
        )

    @staticmethod
    def _aggregate_by_config(
        summaries: list[EvaluationSummary],
        configs: Iterable[AblationConfig],
    ) -> tuple[ConfigAggregate, ...]:
        results: list[ConfigAggregate] = []
        for ablation_cfg in configs:
            cfg_rows = [s for s in summaries if s.config_label == ablation_cfg.label]
            if not cfg_rows:
                continue
            n = len(cfg_rows)
            results.append(
                ConfigAggregate(
                    config_label=ablation_cfg.label,
                    description=ablation_cfg.description,
                    avg_meter_accuracy=sum(r.meter_accuracy for r in cfg_rows) / n,
                    avg_rhyme_accuracy=sum(r.rhyme_accuracy for r in cfg_rows) / n,
                    avg_iterations=sum(r.num_iterations for r in cfg_rows) / n,
                    error_count=sum(1 for r in cfg_rows if r.error),
                    total_runs=n,
                )
            )
        return tuple(results)

    @staticmethod
    def _aggregate_by_category(
        summaries: list[EvaluationSummary],
        scenarios: Iterable[EvaluationScenario],
    ) -> tuple[CategoryAggregate, ...]:
        scenario_list = list(scenarios)
        results: list[CategoryAggregate] = []
        for cat in ScenarioCategory:
            cat_ids = {s.id for s in scenario_list if s.category == cat}
            cat_rows = [s for s in summaries if s.scenario_id in cat_ids]
            if not cat_rows:
                continue
            n = len(cat_rows)
            results.append(
                CategoryAggregate(
                    category=cat.value,
                    total_runs=n,
                    avg_meter_accuracy=sum(r.meter_accuracy for r in cat_rows) / n,
                    avg_rhyme_accuracy=sum(r.rhyme_accuracy for r in cat_rows) / n,
                    error_count=sum(1 for r in cat_rows if r.error),
                )
            )
        return tuple(results)
