"""Tracing ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.evaluation import (
        IterationRecord,
        MetricValue,
        PipelineTrace,
        StageRecord,
    )


class ITraceRecorder(ABC):
    """Write-only port for accumulating pipeline trace events."""

    @abstractmethod
    def add_stage(self, stage: StageRecord) -> None: ...

    @abstractmethod
    def add_iteration(self, iteration: IterationRecord) -> None: ...

    @abstractmethod
    def set_final_poem(self, poem: str) -> None: ...

    @abstractmethod
    def set_final_metrics(self, metrics: dict[str, MetricValue]) -> None: ...

    @abstractmethod
    def set_total_duration(self, duration_sec: float) -> None: ...

    @abstractmethod
    def set_error(self, error: str | None) -> None: ...


class ITraceReader(ABC):
    """Read-only port for querying accumulated pipeline trace state."""

    @abstractmethod
    def iterations(self) -> tuple[IterationRecord, ...]: ...

    @abstractmethod
    def get_trace(self) -> PipelineTrace: ...


class ITracer(ITraceRecorder, ITraceReader):
    """Combined read + write tracer facade."""


class ITracerFactory(ABC):
    """Creates fresh ITracer instances for each evaluation run."""

    @abstractmethod
    def create(self, scenario_id: str, config_label: str) -> ITracer: ...
