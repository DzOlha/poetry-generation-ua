"""Pydantic request/response schemas for the FastAPI handler layer.

Schemas are pure data containers: they own JSON validation and translation
to/from domain objects only. Formatting structured `LineFeedback` /
`PairFeedback` into strings is a router-level concern (the router owns the
`IFeedbackFormatter` dependency) so schemas stay free of port dependencies.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    MeterSpec,
    PoemStructure,
    RhymeScheme,
    ValidationRequest,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Nested schema components
# ---------------------------------------------------------------------------

class MeterSpecSchema(BaseModel):
    name: str = Field(default="ямб")
    foot_count: int = Field(default=4, ge=1, le=10)

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
    stanza_count: int = Field(default=4, ge=1, le=20)
    lines_per_stanza: int = Field(default=4, ge=2, le=10)

    def to_domain(self) -> PoemStructure:
        return PoemStructure(stanza_count=self.stanza_count, lines_per_stanza=self.lines_per_stanza)

    @classmethod
    def from_domain(cls, s: PoemStructure) -> PoemStructureSchema:
        return cls(stanza_count=s.stanza_count, lines_per_stanza=s.lines_per_stanza)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class GenerationRequestSchema(BaseModel):
    theme: str = Field(..., min_length=1)
    meter: MeterSpecSchema = Field(default_factory=MeterSpecSchema)
    rhyme: RhymeSchemeSchema = Field(default_factory=RhymeSchemeSchema)
    structure: PoemStructureSchema = Field(default_factory=PoemStructureSchema)
    max_iterations: int = Field(default=3, ge=0, le=10)
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
    poem_text: str = Field(..., min_length=1)
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

    @classmethod
    def from_strings(
        cls,
        r: ValidationResult,
        meter_msgs: list[str],
        rhyme_msgs: list[str],
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
        )


# ---------------------------------------------------------------------------
# Detection schemas
# ---------------------------------------------------------------------------

class DetectionRequestSchema(BaseModel):
    poem_text: str = Field(..., min_length=1)
    sample_lines: int | None = Field(default=None, ge=2, le=14)


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


class DetectionResultSchema(BaseModel):
    meter: MeterDetectionSchema | None
    rhyme: RhymeDetectionSchema | None
    is_detected: bool

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

class GenerationResultSchema(BaseModel):
    poem: str
    validation: ValidationResultSchema

    @classmethod
    def from_strings(
        cls,
        r: GenerationResult,
        meter_msgs: list[str],
        rhyme_msgs: list[str],
    ) -> GenerationResultSchema:
        return cls(
            poem=r.poem,
            validation=ValidationResultSchema.from_strings(
                r.validation, meter_msgs, rhyme_msgs,
            ),
        )
