"""Pydantic request/response schemas for the FastAPI handler layer.

Schemas are pure data containers: they own JSON validation and translation
to/from domain objects only. Formatting structured `LineFeedback` /
`PairFeedback` into strings is a router-level concern (the router owns the
`IFeedbackFormatter` dependency) so schemas stay free of port dependencies.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.config import LLMInfo
from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.evaluation import (
    AblationConfig,
    IterationRecord,
    PipelineTrace,
    StageRecord,
)
from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    IterationSnapshot,
    LineMeterResult,
    MeterSpec,
    PoemStructure,
    RhymeScheme,
    ValidationRequest,
    ValidationResult,
)
from src.domain.scenarios import EvaluationScenario
from src.handlers.shared.line_displays import line_displays

# ---------------------------------------------------------------------------
# System metadata
# ---------------------------------------------------------------------------

class LLMInfoSchema(BaseModel):
    """Active LLM provider/model + readiness flag.

    Mirrors `LLMInfo` so SPAs can render the same "provider · model" badge
    and "Generation unavailable: <error>" banner the HTML form pages show
    (`generate.html`, `evaluate.html`). The `ready` flag is what the
    server-side handler checks before letting a generation request reach
    the pipeline; SPAs should mirror that behaviour and disable their
    submit button when `ready` is False.
    """

    provider: str
    model: str
    ready: bool
    error: str | None = None

    @classmethod
    def from_domain(cls, info: LLMInfo) -> LLMInfoSchema:
        return cls(
            provider=info.provider,
            model=info.model,
            ready=info.ready,
            error=info.error,
        )


# ---------------------------------------------------------------------------
# Nested schema components
# ---------------------------------------------------------------------------

class MeterSpecSchema(BaseModel):
    name: str = Field(default="ямб")
    foot_count: int = Field(default=4, ge=1, le=6)

    def to_domain(self) -> MeterSpec:
        return MeterSpec(name=self.name, foot_count=self.foot_count)

    @classmethod
    def from_domain(cls, m: MeterSpec) -> MeterSpecSchema:
        return cls(name=m.name, foot_count=m.foot_count)


class RhymeSchemeSchema(BaseModel):
    pattern: str = Field(default="ABAB")

    def to_domain(self) -> RhymeScheme:
        return RhymeScheme(pattern=self.pattern)

    @classmethod
    def from_domain(cls, s: RhymeScheme) -> RhymeSchemeSchema:
        return cls(pattern=s.pattern)


class PoemStructureSchema(BaseModel):
    stanza_count: int = Field(default=4, ge=1, le=5)
    lines_per_stanza: Literal[4] = 4

    def to_domain(self) -> PoemStructure:
        return PoemStructure(stanza_count=self.stanza_count, lines_per_stanza=self.lines_per_stanza)

    @classmethod
    def from_domain(cls, s: PoemStructure) -> PoemStructureSchema:
        return cls(stanza_count=s.stanza_count)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class GenerationRequestSchema(BaseModel):
    theme: str = Field(..., min_length=1, max_length=200)
    meter: MeterSpecSchema = Field(default_factory=MeterSpecSchema)
    rhyme: RhymeSchemeSchema = Field(default_factory=RhymeSchemeSchema)
    structure: PoemStructureSchema = Field(default_factory=PoemStructureSchema)
    max_iterations: int = Field(default=3, ge=0, le=3)
    top_k: int = Field(default=5, ge=1, le=20)
    metric_examples_top_k: int = Field(default=3, ge=0, le=10)

    def to_domain(self) -> GenerationRequest:
        return GenerationRequest(
            theme=self.theme,
            meter=self.meter.to_domain(),
            rhyme=self.rhyme.to_domain(),
            structure=self.structure.to_domain(),
            max_iterations=self.max_iterations,
            top_k=self.top_k,
            metric_examples_top_k=self.metric_examples_top_k,
        )


class ValidationRequestSchema(BaseModel):
    poem_text: str = Field(..., min_length=1, max_length=5000)
    meter: MeterSpecSchema = Field(default_factory=MeterSpecSchema)
    rhyme: RhymeSchemeSchema = Field(default_factory=RhymeSchemeSchema)

    def to_domain(self) -> ValidationRequest:
        return ValidationRequest(
            poem_text=self.poem_text,
            meter=self.meter.to_domain(),
            rhyme=self.rhyme.to_domain(),
        )


# ---------------------------------------------------------------------------
# Response schemas — pure data, formatting lives in the router.
# ---------------------------------------------------------------------------

class LineSegmentSchema(BaseModel):
    """A single character of a poem line tagged with its stress role.

    `tag` is one of: "" (no stress role), "exp" (expected by meter),
    "act" (actual stress detected), "both" (matches — expected == actual).
    An SPA can render these verbatim with one CSS class per tag.
    """
    ch: str
    tag: Literal["", "exp", "act", "both"]


class LineDisplaySchema(BaseModel):
    """Per-line render payload: text, ok-flag, char-level stress segments, notes.

    `blank=True` means the source text had an empty line here (stanza break).
    When `blank=False`, `text` is the stripped line and `segments` is the
    full char-by-char decomposition. `length_note` and `annotation` are
    pre-formatted human-readable explanations of the violation, if any.
    """
    blank: bool = False
    text: str | None = None
    ok: bool | None = None
    segments: list[LineSegmentSchema] | None = None
    length_note: str | None = None
    annotation: str | None = None

    @classmethod
    def list_from(
        cls,
        poem_text: str,
        line_results: tuple[LineMeterResult, ...],
    ) -> list[LineDisplaySchema]:
        """Build a list of LineDisplaySchema from raw text + meter line_results."""
        raw = line_displays(poem_text, line_results)
        return [cls.model_validate(d) for d in raw]


class MeterResultSchema(BaseModel):
    ok: bool
    accuracy: float
    feedback: list[str]


class RhymeResultSchema(BaseModel):
    ok: bool
    accuracy: float
    feedback: list[str]


class ValidationResultSchema(BaseModel):
    is_valid: bool
    meter: MeterResultSchema
    rhyme: RhymeResultSchema
    iterations: int
    feedback: list[str]
    # Per-line annotated display — char-level stress segments + length notes.
    # An SPA uses this to render the highlighted poem without re-implementing
    # the vowel-indexing / stress-matching logic client-side.
    line_displays: list[LineDisplaySchema] = Field(default_factory=list)

    @classmethod
    def from_strings(
        cls,
        r: ValidationResult,
        meter_msgs: list[str],
        rhyme_msgs: list[str],
        poem_text: str = "",
    ) -> ValidationResultSchema:
        return cls(
            is_valid=r.is_valid,
            meter=MeterResultSchema(
                ok=r.meter.ok, accuracy=r.meter.accuracy, feedback=meter_msgs,
            ),
            rhyme=RhymeResultSchema(
                ok=r.rhyme.ok, accuracy=r.rhyme.accuracy, feedback=rhyme_msgs,
            ),
            iterations=r.iterations,
            feedback=meter_msgs + rhyme_msgs,
            line_displays=LineDisplaySchema.list_from(
                poem_text, r.meter.line_results,
            ) if poem_text else [],
        )


# ---------------------------------------------------------------------------
# Detection schemas
# ---------------------------------------------------------------------------

class DetectionRequestSchema(BaseModel):
    poem_text: str = Field(..., min_length=1, max_length=5000)
    sample_lines: int | None = Field(default=4, ge=4, le=4)
    # Mirror the web form — let SPAs pick which aspect(s) to detect. Both
    # default to true, matching the existing sole-purpose JSON endpoint.
    detect_meter: bool = Field(default=True)
    detect_rhyme: bool = Field(default=True)


class MeterDetectionSchema(BaseModel):
    meter: str
    foot_count: int
    accuracy: float

    @classmethod
    def from_domain(cls, d: MeterDetection) -> MeterDetectionSchema:
        return cls(meter=d.meter, foot_count=d.foot_count, accuracy=d.accuracy)


class RhymeDetectionSchema(BaseModel):
    scheme: str
    accuracy: float

    @classmethod
    def from_domain(cls, d: RhymeDetection) -> RhymeDetectionSchema:
        return cls(scheme=d.scheme, accuracy=d.accuracy)


class StanzaDetectionSchema(BaseModel):
    """Per-stanza detection result — mirrors the web's `stanza_displays`."""
    meter: MeterDetectionSchema | None = None
    rhyme: RhymeDetectionSchema | None = None
    meter_accuracy: float | None = None
    rhyme_accuracy: float | None = None
    lines_count: int = 0
    line_displays: list[LineDisplaySchema] = Field(default_factory=list)


class DetectionResultSchema(BaseModel):
    meter: MeterDetectionSchema | None
    rhyme: RhymeDetectionSchema | None
    is_detected: bool
    poem_text: str = ""
    validated_lines: int = 0
    want_meter: bool = True
    want_rhyme: bool = True
    stanzas: list[StanzaDetectionSchema] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, r: DetectionResult) -> DetectionResultSchema:
        return cls(
            meter=MeterDetectionSchema.from_domain(r.meter) if r.meter else None,
            rhyme=RhymeDetectionSchema.from_domain(r.rhyme) if r.rhyme else None,
            is_detected=r.is_detected,
        )


# ---------------------------------------------------------------------------
# Generation response schemas
# ---------------------------------------------------------------------------

class IterationSnapshotSchema(BaseModel):
    iteration: int
    poem: str
    meter_accuracy: float
    rhyme_accuracy: float
    feedback: list[str]
    duration_sec: float
    # Per-line annotated display for this iteration's poem snapshot.
    # Empty when the snapshot can't be re-validated (e.g. domain error).
    line_displays: list[LineDisplaySchema] = Field(default_factory=list)
    raw_llm_response: str = ""
    sanitized_llm_response: str = ""
    # Per-iteration token usage reported by the LLM provider. 0 when
    # the provider did not surface usage metadata (mock adapter, safety
    # block, SDK drift).
    input_tokens: int = 0
    output_tokens: int = 0

    @classmethod
    def from_domain(cls, s: IterationSnapshot) -> IterationSnapshotSchema:
        return cls(
            iteration=s.iteration,
            poem=s.poem,
            meter_accuracy=s.meter_accuracy,
            rhyme_accuracy=s.rhyme_accuracy,
            feedback=list(s.feedback),
            duration_sec=s.duration_sec,
            raw_llm_response=s.raw_llm_response,
            sanitized_llm_response=s.sanitized_llm_response,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
        )


class GenerationResultSchema(BaseModel):
    poem: str
    theme: str = ""
    validation: ValidationResultSchema
    iteration_history: list[IterationSnapshotSchema] = Field(default_factory=list)
    # Server-computed extra metrics (semantic_relevance, regeneration_success,
    # num_lines, feedback_iterations). Keys depend on which IMetricCalculator
    # instances are registered — SPAs should treat this as a string→number map.
    extra_metrics: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def from_strings(
        cls,
        r: GenerationResult,
        meter_msgs: list[str],
        rhyme_msgs: list[str],
        theme: str = "",
        extra_metrics: dict[str, float] | None = None,
        iteration_displays: list[list[LineDisplaySchema]] | None = None,
    ) -> GenerationResultSchema:
        snapshots = [
            IterationSnapshotSchema.from_domain(s) for s in r.iteration_history
        ]
        if iteration_displays is not None:
            for snap, disp in zip(snapshots, iteration_displays, strict=False):
                snap.line_displays = disp
        return cls(
            poem=r.poem,
            theme=theme,
            validation=ValidationResultSchema.from_strings(
                r.validation, meter_msgs, rhyme_msgs, poem_text=r.poem,
            ),
            iteration_history=snapshots,
            extra_metrics=extra_metrics or {},
        )


# ---------------------------------------------------------------------------
# Evaluation schemas — expose scenario registry, ablation configs, and the
# full PipelineTrace so an SPA can render the same stage-by-stage UI the
# HTML evaluate_result.html shows.
# ---------------------------------------------------------------------------

class ScenarioSchema(BaseModel):
    id: str
    name: str
    category: str
    theme: str
    meter: str
    foot_count: int
    rhyme_scheme: str
    stanza_count: int
    lines_per_stanza: int

    @classmethod
    def from_domain(cls, s: EvaluationScenario) -> ScenarioSchema:
        return cls(
            id=s.id,
            name=s.name,
            category=s.category.value if hasattr(s.category, "value") else str(s.category),
            theme=s.theme,
            meter=s.meter,
            foot_count=s.foot_count,
            rhyme_scheme=s.rhyme_scheme,
            stanza_count=s.stanza_count,
            lines_per_stanza=s.lines_per_stanza,
        )


class ScenariosByCategorySchema(BaseModel):
    """Scenarios grouped by category (normal / edge / corner).

    Mirrors the `scenarios_by_cat(...)` helper the HTML `evaluate.html`
    page consumes so an SPA can render the same three-column grid
    without grouping a flat list client-side.
    """

    normal: list[ScenarioSchema] = Field(default_factory=list)
    edge: list[ScenarioSchema] = Field(default_factory=list)
    corner: list[ScenarioSchema] = Field(default_factory=list)


class AblationConfigSchema(BaseModel):
    label: str
    description: str
    enabled_stages: list[str]

    @classmethod
    def from_domain(cls, c: AblationConfig) -> AblationConfigSchema:
        return cls(
            label=c.label,
            description=c.description,
            enabled_stages=sorted(c.enabled_stages),
        )


class EvaluationRunRequestSchema(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    config_label: str = Field(default="E", min_length=1)
    max_iterations: int = Field(default=1, ge=0, le=3)


class StageRecordSchema(BaseModel):
    """One pipeline stage — mirrors `StageRecord` plus pretty-printed data."""
    name: str
    input_summary: str = ""
    output_summary: str = ""
    input_data: Any = None
    output_data: Any = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    duration_sec: float = 0.0
    error: str | None = None

    @classmethod
    def from_domain(cls, s: StageRecord) -> StageRecordSchema:
        return cls(
            name=s.name,
            input_summary=s.input_summary,
            output_summary=s.output_summary,
            input_data=s.input_data,
            output_data=s.output_data,
            metrics=dict(s.metrics),
            duration_sec=s.duration_sec,
            error=s.error,
        )


class EvaluationIterationSchema(BaseModel):
    iteration: int
    poem_text: str
    meter_accuracy: float
    rhyme_accuracy: float
    feedback: list[str]
    duration_sec: float
    line_displays: list[LineDisplaySchema] = Field(default_factory=list)
    raw_llm_response: str = ""
    sanitized_llm_response: str = ""

    @classmethod
    def from_domain(cls, it: IterationRecord) -> EvaluationIterationSchema:
        return cls(
            iteration=it.iteration,
            poem_text=it.poem_text,
            meter_accuracy=it.meter_accuracy,
            rhyme_accuracy=it.rhyme_accuracy,
            feedback=list(it.feedback),
            duration_sec=it.duration_sec,
            raw_llm_response=it.raw_llm_response,
            sanitized_llm_response=it.sanitized_llm_response,
        )


class PipelineTraceSchema(BaseModel):
    scenario_id: str
    config_label: str
    final_poem: str
    error: str | None = None
    total_duration_sec: float = 0.0
    final_metrics: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageRecordSchema] = Field(default_factory=list)
    iterations: list[EvaluationIterationSchema] = Field(default_factory=list)
    final_line_displays: list[LineDisplaySchema] = Field(default_factory=list)

    @classmethod
    def from_domain(
        cls,
        trace: PipelineTrace,
        *,
        final_line_displays: list[LineDisplaySchema] | None = None,
        iteration_line_displays: list[list[LineDisplaySchema]] | None = None,
    ) -> PipelineTraceSchema:
        iters = [EvaluationIterationSchema.from_domain(i) for i in trace.iterations]
        if iteration_line_displays is not None:
            for it, disp in zip(iters, iteration_line_displays, strict=False):
                it.line_displays = disp
        return cls(
            scenario_id=trace.scenario_id,
            config_label=trace.config_label,
            final_poem=trace.final_poem,
            error=trace.error,
            total_duration_sec=trace.total_duration_sec,
            final_metrics=dict(trace.final_metrics),
            stages=[StageRecordSchema.from_domain(s) for s in trace.stages],
            iterations=iters,
            final_line_displays=final_line_displays or [],
        )


class EvaluationRunResponseSchema(BaseModel):
    scenario: ScenarioSchema
    config: AblationConfigSchema
    trace: PipelineTraceSchema


# ---------------------------------------------------------------------------
# Ablation-report schemas — JSON twin of the HTML `/ablation-report` page.
# ---------------------------------------------------------------------------

class ComponentExplanationSchema(BaseModel):
    """One row of the component glossary shown on the ablation dashboard."""

    name: str
    label: str
    comparison: str
    summary: str
    interpretation: str


class PlotExplanationSchema(BaseModel):
    """Static methodology caption for one plot — same across all batches."""

    title: str
    what: str
    how_to_read: str
    look_for: str


class PlotAnalysisSchema(BaseModel):
    """Per-batch auto-generated narrative analysis derived from the numbers.

    `summary` and entries in `bullets` may contain inline HTML markup
    (`<code>`, `<b>`) for template rendering — SPAs should either render
    as HTML or strip the tags client-side.
    """

    summary: str
    bullets: list[str] = Field(default_factory=list)
    empty: bool = False


class AblationInsightLineSchema(BaseModel):
    """One bullet of the headline insights block — one (component, metric) pair."""

    component: str
    metric_key: str
    metric_label: str
    mean: str
    ci: str
    verdict: str
    tone: Literal["positive", "negative", "neutral"]


class AblationInsightsSchema(BaseModel):
    """Top-level narrative summary derived from the contributions table."""

    headline: str
    component_lines: list[AblationInsightLineSchema] = Field(default_factory=list)
    cost_lines: list[str] = Field(default_factory=list)


class AblationReportResponseSchema(BaseModel):
    """JSON twin of the HTML `/ablation-report` page payload.

    Mirrors :class:`src.handlers.shared.ablation_report.BatchArtifacts`.
    SPAs use this to render the same dashboard the web UI shows: glossary
    + plot URLs + per-plot narrative + scenario/config catalogues + headline
    insights, all derived from the latest `results/batch_*/` folder.
    """

    batch_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    contributions: list[dict[str, Any]] = Field(default_factory=list)
    contributions_by_cat: list[dict[str, Any]] = Field(default_factory=list)
    plot_urls: dict[str, str] = Field(default_factory=dict)
    components: list[ComponentExplanationSchema] = Field(default_factory=list)
    plot_explanations: dict[str, PlotExplanationSchema] = Field(default_factory=dict)
    plot_analyses: dict[str, PlotAnalysisSchema] = Field(default_factory=dict)
    scenarios_by_category: list[dict[str, Any]] = Field(default_factory=list)
    configs: list[dict[str, Any]] = Field(default_factory=list)
    insights: AblationInsightsSchema

