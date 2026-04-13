"""Evaluation sub-container.

Owns the scenario registry port and the evaluation `IPipeline` that
wires in the `FinalMetricsStage`. Anything specific to the evaluation
matrix (as opposed to interactive generation) lives here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import IPipeline, IScenarioRegistry
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.evaluation import StaticScenarioRegistry
from src.infrastructure.pipeline import SequentialPipeline

if TYPE_CHECKING:
    from src.composition_root import Container


class EvaluationSubContainer:
    """Scenario registry + evaluation pipeline (with final metrics)."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def scenario_registry(self) -> IScenarioRegistry:
        return self._parent._get(CacheKey.SCENARIO_REGISTRY, StaticScenarioRegistry)

    def evaluation_pipeline(self) -> IPipeline:
        return self._parent._get(
            CacheKey.EVALUATION_PIPELINE,
            lambda: SequentialPipeline(
                stages=self._parent.generation.stage_factory().build_for(
                    frozenset(),
                ),
                final_metrics_stage=self._parent.metrics.final_metrics_stage(),
            ),
        )
