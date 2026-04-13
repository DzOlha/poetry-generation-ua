"""Evaluation domain objects — ablation configs, traces, and summaries.

`AblationConfig.enabled_stages` holds canonical stage names as a frozen set.
Stages themselves declare their `IPipelineStage.name`; `IStageSkipPolicy`
consults `AblationConfig.is_enabled(stage.name)` to decide whether a
togglable stage should run. No more back-compat `use_*` properties.

Frozen dataclasses below are value objects. Mutable accumulation during a
run lives in `infrastructure.tracing.PipelineTracer` and is published as a
fresh `PipelineTrace` snapshot via `ITracer.get_trace()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Stage I/O data is intentionally `Any` — each stage writes a different
# shape (list[dict], str, None).  Metrics are narrower: float | int.
MetricValue = float | int

# ---------------------------------------------------------------------------
# Ablation configurations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AblationConfig:
    """Defines which pipeline stages are active in one ablation variant.

    `enabled_stages` must contain the canonical stage names that callers
    want active. Mandatory stages (prompt construction, LLM generation,
    final metrics) ignore ablation toggles and always run — `IStageSkipPolicy`
    knows which stages are togglable.
    """

    label: str
    enabled_stages: frozenset[str]
    description: str = ""

    def is_enabled(self, stage_name: str) -> bool:
        return stage_name in self.enabled_stages


# Canonical stage names — kept here so `ABLATION_CONFIGS` and the stage
# factory share a single source of truth.
STAGE_RETRIEVAL = "retrieval"
STAGE_METRIC_EXAMPLES = "metric_examples"
STAGE_PROMPT_CONSTRUCTION = "prompt_construction"
STAGE_INITIAL_GENERATION = "initial_generation"
STAGE_VALIDATION = "validation"
STAGE_FEEDBACK_LOOP = "feedback_loop"
STAGE_FINAL_METRICS = "final_metrics"


ABLATION_CONFIGS: list[AblationConfig] = [
    AblationConfig(
        label="A",
        enabled_stages=frozenset({STAGE_VALIDATION}),
        description="Baseline (LLM + validator, no RAG, no feedback)",
    ),
    AblationConfig(
        label="B",
        enabled_stages=frozenset({STAGE_VALIDATION, STAGE_FEEDBACK_LOOP}),
        description="LLM + Val + Feedback (no RAG)",
    ),
    AblationConfig(
        label="C",
        enabled_stages=frozenset({STAGE_RETRIEVAL, STAGE_VALIDATION, STAGE_FEEDBACK_LOOP}),
        description="Semantic RAG + Val + Feedback",
    ),
    AblationConfig(
        label="D",
        enabled_stages=frozenset({STAGE_METRIC_EXAMPLES, STAGE_VALIDATION, STAGE_FEEDBACK_LOOP}),
        description="Metric Examples + Val + Feedback",
    ),
    AblationConfig(
        label="E",
        enabled_stages=frozenset({
            STAGE_RETRIEVAL,
            STAGE_METRIC_EXAMPLES,
            STAGE_VALIDATION,
            STAGE_FEEDBACK_LOOP,
        }),
        description="Full system (semantic + metric examples + val + feedback)",
    ),
]

# Default configuration used by PoetryService.generate — every togglable
# stage is enabled. Kept in the domain layer because it is a value, not a
# wiring concern.
DEFAULT_GENERATION_CONFIG = AblationConfig(
    label="generate",
    enabled_stages=frozenset({
        STAGE_RETRIEVAL,
        STAGE_METRIC_EXAMPLES,
        STAGE_VALIDATION,
        STAGE_FEEDBACK_LOOP,
    }),
    description="Interactive / API generation: everything on, no tracing.",
)


# ---------------------------------------------------------------------------
# Evaluation summary (one row per scenario × config run)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationSummary:
    """Aggregated result for a single (scenario, config) run."""

    scenario_id: str
    scenario_name: str
    config_label: str
    meter: str
    foot_count: int
    rhyme_scheme: str
    meter_accuracy: float
    rhyme_accuracy: float
    num_iterations: int
    num_lines: int
    duration_sec: float
    error: str | None = None


# ---------------------------------------------------------------------------
# Pipeline trace (full stage-by-stage execution record)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StageRecord:
    """Record for a single stage of a traced pipeline run."""

    name: str
    input_summary: str = ""
    output_summary: str = ""
    input_data: Any = None
    output_data: Any = None
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    duration_sec: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class IterationRecord:
    """Record for one feedback-loop iteration."""

    iteration: int
    poem_text: str
    meter_accuracy: float
    rhyme_accuracy: float
    feedback: tuple[str, ...]
    duration_sec: float = 0.0


@dataclass(frozen=True)
class PipelineTrace:
    """Immutable snapshot of a single (scenario, config) pipeline run."""

    scenario_id: str
    config_label: str
    stages: tuple[StageRecord, ...] = ()
    iterations: tuple[IterationRecord, ...] = ()
    final_poem: str = ""
    final_metrics: dict[str, MetricValue] = field(default_factory=dict)
    total_duration_sec: float = 0.0
    error: str | None = None
