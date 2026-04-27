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
    # ── No-feedback variants (F, G, H) ─────────────────────────────────
    # When feedback is enabled in both arms of a comparison, the loop
    # iteratively repairs the initial draft and the contribution of an
    # enrichment stage (RAG / metric examples) gets masked — both
    # configs converge on similar final quality. These three configs
    # mirror C / D / E with feedback OFF, so paired-Δ vs. A measures the
    # *raw* effect of an enrichment on the first-attempt poem.
    AblationConfig(
        label="F",
        enabled_stages=frozenset({STAGE_RETRIEVAL, STAGE_VALIDATION}),
        description="Semantic RAG + Val (no feedback) — pure RAG effect",
    ),
    AblationConfig(
        label="G",
        enabled_stages=frozenset({STAGE_METRIC_EXAMPLES, STAGE_VALIDATION}),
        description="Metric Examples + Val (no feedback) — pure metric-examples effect",
    ),
    AblationConfig(
        label="H",
        enabled_stages=frozenset({
            STAGE_RETRIEVAL,
            STAGE_METRIC_EXAMPLES,
            STAGE_VALIDATION,
        }),
        description="Semantic + Metric Examples + Val (no feedback) — pure combined effect",
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
    # Token + cost totals across every LLM call in this run (initial
    # generation + feedback iterations). 0 when the provider does not
    # expose usage metadata (mock adapters, safety blocks).
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
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
    # Debug trace: raw provider output and post-sanitizer text for the
    # LLM call that produced this iteration. Empty when no LLM call was
    # observed (e.g. mock providers that bypass the decorator stack).
    raw_llm_response: str = ""
    sanitized_llm_response: str = ""
    # Token usage reported by the LLM provider for this iteration's
    # single generate/regenerate call. 0 means "not available" (mock
    # adapter, safety block, SDK drift) — consumers treat it as unknown,
    # not as a free call.
    input_tokens: int = 0
    output_tokens: int = 0
    # User-facing error message when this iteration failed (LLM error,
    # quota, network, etc). When set, accuracy fields hold the *previous*
    # iteration's metrics — the failed call did not produce a new poem,
    # so validation kept the prior result. UI must surface this so users
    # don't think regeneration silently succeeded with the same numbers.
    error: str | None = None


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


# ---------------------------------------------------------------------------
# Batch evaluation — one flat row per (scenario, config, seed) run
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BatchRunRow:
    """One row in the flat batch-run CSV consumed by downstream analysis."""

    scenario_id: str
    scenario_name: str
    category: str
    meter: str
    foot_count: int
    rhyme_scheme: str
    config_label: str
    config_description: str
    seed: int
    meter_accuracy: float
    rhyme_accuracy: float
    regeneration_success: float
    semantic_relevance: float
    num_iterations: int
    num_lines: int
    duration_sec: float
    # Token + cost instrumentation. Totals across all LLM calls in the run
    # (initial generation + every feedback iteration). ``iteration_tokens``
    # is the per-iteration breakdown serialised as
    # ``it=<idx>:in=<n>:out=<n>,it=…`` so the CSV stays a flat row yet
    # keeps the per-call information analysts may want.
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    iteration_tokens: str = ""
    error: str | None = None
