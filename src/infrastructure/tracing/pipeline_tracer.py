"""ITracer / ITracerFactory implementations.

PipelineTracer is the *mutable accumulator* that pipeline stages write into.
It owns lists of StageRecord / IterationRecord plus loose top-level fields
(final_poem, final_metrics, total_duration, error). On every `get_trace()`
call it produces a fresh, frozen `PipelineTrace` snapshot — the value
object that crosses service boundaries.

Domain `PipelineTrace` is intentionally immutable; the mutability lives
here in infrastructure where it belongs.
"""
from __future__ import annotations

from src.domain.evaluation import IterationRecord, MetricValue, PipelineTrace, StageRecord
from src.domain.ports import ITracer, ITracerFactory


class PipelineTracer(ITracer):
    """Mutable trace accumulator producing immutable PipelineTrace snapshots."""

    def __init__(self, scenario_id: str, config_label: str) -> None:
        self._scenario_id = scenario_id
        self._config_label = config_label
        self._stages: list[StageRecord] = []
        self._iterations: list[IterationRecord] = []
        self._final_poem: str = ""
        self._final_metrics: dict[str, MetricValue] = {}
        self._total_duration: float = 0.0
        self._error: str | None = None

    # ------------------------------------------------------------------
    # ITracer write API
    # ------------------------------------------------------------------

    def add_stage(self, stage: StageRecord) -> None:
        self._stages.append(stage)

    def add_iteration(self, iteration: IterationRecord) -> None:
        self._iterations.append(iteration)

    def set_final_poem(self, poem: str) -> None:
        self._final_poem = poem

    def set_final_metrics(self, metrics: dict[str, MetricValue]) -> None:
        self._final_metrics = dict(metrics)

    def set_total_duration(self, duration_sec: float) -> None:
        self._total_duration = duration_sec

    def set_error(self, error: str | None) -> None:
        self._error = error

    # ------------------------------------------------------------------
    # ITracer read API
    # ------------------------------------------------------------------

    def iterations(self) -> tuple[IterationRecord, ...]:
        return tuple(self._iterations)

    def get_trace(self) -> PipelineTrace:
        """Return a frozen snapshot of the accumulated trace."""
        return PipelineTrace(
            scenario_id=self._scenario_id,
            config_label=self._config_label,
            stages=tuple(self._stages),
            iterations=tuple(self._iterations),
            final_poem=self._final_poem,
            final_metrics=dict(self._final_metrics),
            total_duration_sec=self._total_duration,
            error=self._error,
        )


class PipelineTracerFactory(ITracerFactory):
    """Creates a fresh PipelineTracer for every evaluation run."""

    def create(self, scenario_id: str, config_label: str) -> ITracer:
        return PipelineTracer(scenario_id=scenario_id, config_label=config_label)
