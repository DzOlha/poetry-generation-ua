"""Null-object ITracer — used by PoetryService and tests that don't care about trace output.

`NullTracer` accepts every write, remembers nothing except the final poem +
final error so `PoetryService.generate` can still find out whether the run
was aborted, and produces a minimal snapshot on `get_trace()`. It lets the
same `IPipeline` drive both evaluation (with full tracing) and interactive
generation (tracing off) without branching in every stage.
"""
from __future__ import annotations

from src.domain.evaluation import IterationRecord, MetricValue, PipelineTrace, StageRecord
from src.domain.ports import ITracer


class NullTracer(ITracer):
    """ITracer that records only the minimum PoetryService needs: poem + error."""

    def __init__(self) -> None:
        self._final_poem: str = ""
        self._error: str | None = None
        self._iterations: tuple[IterationRecord, ...] = ()

    def add_stage(self, stage: StageRecord) -> None:
        return None

    def add_iteration(self, iteration: IterationRecord) -> None:
        # Keep the iteration history so the feedback iterator can compute deltas.
        self._iterations = (*self._iterations, iteration)

    def set_final_poem(self, poem: str) -> None:
        self._final_poem = poem

    def set_final_metrics(self, metrics: dict[str, MetricValue]) -> None:
        return None

    def set_total_duration(self, duration_sec: float) -> None:
        return None

    def set_error(self, error: str | None) -> None:
        self._error = error

    def iterations(self) -> tuple[IterationRecord, ...]:
        return self._iterations

    def get_trace(self) -> PipelineTrace:
        return PipelineTrace(
            scenario_id="",
            config_label="",
            final_poem=self._final_poem,
            iterations=self._iterations,
            error=self._error,
        )
