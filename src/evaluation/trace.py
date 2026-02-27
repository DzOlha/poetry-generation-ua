"""Pipeline trace — records the input / output of every stage.

A traced pipeline run produces a ``PipelineTrace`` containing an ordered
list of ``StageRecord`` objects (one per stage) plus aggregated metrics.
The trace can be serialised to a plain dict for JSON export.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageRecord:
    """Single pipeline stage record."""

    name: str
    input_summary: str = ""
    output_summary: str = ""
    input_data: Any = None
    output_data: Any = None
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_sec: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "stage": self.name,
            "input": self.input_summary,
            "output": self.output_summary,
            "metrics": self.metrics,
            "duration_sec": round(self.duration_sec, 4),
        }
        if self.input_data is not None:
            d["input_data"] = self.input_data
        if self.output_data is not None:
            d["output_data"] = self.output_data
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class IterationRecord:
    """One feedback-loop iteration."""

    iteration: int
    poem_text: str
    meter_accuracy: float
    rhyme_accuracy: float
    feedback: list[str]
    duration_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "poem_text": self.poem_text,
            "meter_accuracy": round(self.meter_accuracy, 4),
            "rhyme_accuracy": round(self.rhyme_accuracy, 4),
            "feedback": self.feedback,
            "duration_sec": round(self.duration_sec, 4),
        }


@dataclass
class PipelineTrace:
    """Full trace of a single pipeline run."""

    scenario_id: str
    config_label: str
    stages: list[StageRecord] = field(default_factory=list)
    iterations: list[IterationRecord] = field(default_factory=list)
    final_poem: str = ""
    total_duration_sec: float = 0.0
    final_metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def add_stage(self, record: StageRecord) -> None:
        self.stages.append(record)

    def add_iteration(self, record: IterationRecord) -> None:
        self.iterations.append(record)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "scenario_id": self.scenario_id,
            "config": self.config_label,
            "stages": [s.to_dict() for s in self.stages],
            "iterations": [it.to_dict() for it in self.iterations],
            "final_poem": self.final_poem,
            "final_metrics": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in self.final_metrics.items()
            },
            "total_duration_sec": round(self.total_duration_sec, 4),
        }
        if self.error:
            d["error"] = self.error
        return d


class StageTimer:
    """Context manager that measures wall-clock time for a stage."""

    def __init__(self) -> None:
        self.elapsed: float = 0.0
        self._t0: float = 0.0

    def __enter__(self) -> "StageTimer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed = time.perf_counter() - self._t0
