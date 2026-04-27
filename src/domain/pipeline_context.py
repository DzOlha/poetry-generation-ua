"""Pipeline context — the mutable aggregate carried through pipeline stages.

`PipelineState` is the in-process aggregate that links one generation or
evaluation run together. Stages read and write it to communicate with each
other; when the run finishes, its fields describe what happened end-to-end.

The aggregate intentionally lives in the domain layer (not infrastructure)
because every field is a domain concept — request, config, scenario,
retrieved excerpts, meter/rhyme results, feedback, metrics — and every
stage implementation depends on the same shape. Placing it in infrastructure
previously forced services and stages to import across the port boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.domain.evaluation import AblationConfig, MetricValue, PipelineTrace
from src.domain.models import (
    GenerationRequest,
    MeterResult,
    MeterSpec,
    MetricExample,
    RetrievedExcerpt,
    RhymeResult,
    RhymeScheme,
)

if TYPE_CHECKING:
    from src.domain.ports import ITracer
    from src.domain.scenarios import EvaluationScenario


@dataclass
class PipelineState:
    """Shared mutable state for one pipeline run (one scenario × config or one API call).

    This is the single aggregate every `IPipelineStage` reads and writes. It
    lives in the domain because stages are themselves domain use-case
    coordinators; moving it here broke the old service→infrastructure import
    leak flagged by the architectural audit.
    """

    # -- Immutable inputs (set at construction, never mutated) --
    request: GenerationRequest
    config: AblationConfig
    tracer: ITracer
    scenario: EvaluationScenario | None = None

    # -- Stage-owned mutable fields --
    # Each field documents which stage writes it.  Only the owning stage
    # should mutate the field; downstream stages may read it.
    retrieved: list[RetrievedExcerpt] = field(default_factory=list)         # owner: RetrievalStage
    metric_examples: list[MetricExample] = field(default_factory=list)      # owner: MetricExamplesStage
    prompt: str = ""                                                        # owner: PromptStage
    poem: str = ""                                                          # owner: GenerationStage, FeedbackLoopStage
    last_meter_result: MeterResult | None = None                            # owner: ValidationStage, FeedbackLoopStage
    last_rhyme_result: RhymeResult | None = None                            # owner: ValidationStage, FeedbackLoopStage
    cached_feedback: list[str] | None = None                                # owner: ValidationStage, FeedbackLoopStage
    aborted: bool = False                                                   # owner: any stage (via abort())
    abort_reason: str | None = None                                         # owner: any stage (via abort())
    # Original exception that caused the abort, if any. Lets the
    # generation pipeline re-raise the precise type (e.g.
    # `LLMQuotaExceededError`) so the HTTP layer maps it to the right
    # status code (429 vs 502) instead of swallowing it as a string.
    abort_exception: Exception | None = None                                # owner: any stage (via abort())

    # -- Post-run metrics (written by FinalMetricsStage) --
    final_metrics: dict[str, MetricValue] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience accessors — stages can read `state.meter` instead of
    # digging through `state.request.meter` on every call.
    # ------------------------------------------------------------------

    @property
    def theme(self) -> str:
        """Theme string for the scenario / request."""
        if self.scenario is not None:
            return self.scenario.theme
        return self.request.theme

    @property
    def meter(self) -> MeterSpec:
        return self.request.meter

    @property
    def rhyme(self) -> RhymeScheme:
        return self.request.rhyme

    @property
    def max_iterations(self) -> int:
        return self.request.max_iterations

    @property
    def top_k(self) -> int:
        return self.request.top_k

    @property
    def metric_examples_top_k(self) -> int:
        return self.request.metric_examples_top_k

    def abort(self, reason: str, exception: Exception | None = None) -> None:
        """Mark the pipeline as aborted; downstream stages should early-return.

        Pass the originating ``exception`` when the abort was triggered by a
        caught error — the pipeline assembler re-raises it so non-tracing
        callers (interactive /generate) see the real failure instead of an
        empty result.
        """
        self.aborted = True
        self.abort_reason = reason
        self.abort_exception = exception

    def get_trace(self) -> PipelineTrace:
        """Shortcut for `state.tracer.get_trace()`."""
        return self.tracer.get_trace()
