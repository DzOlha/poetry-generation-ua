"""Unit tests for Pydantic request/response schemas and their domain mapping.

Schemas are the edge of the API contract — their `to_domain` / `from_domain`
conversions and field constraints (ge/le bounds, defaults) are asserted
here so breaking changes are caught before routers notice.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.models import (
    GenerationResult,
    IterationSnapshot,
    MeterResult,
    MeterSpec,
    PoemStructure,
    RhymeResult,
    RhymeScheme,
    ValidationResult,
)
from src.handlers.api.schemas import (
    DetectionRequestSchema,
    DetectionResultSchema,
    GenerationRequestSchema,
    GenerationResultSchema,
    MeterSpecSchema,
    PoemStructureSchema,
    RhymeSchemeSchema,
    ValidationRequestSchema,
    ValidationResultSchema,
)

# ---------------------------------------------------------------------------
# MeterSpecSchema
# ---------------------------------------------------------------------------

class TestMeterSpecSchema:
    def test_defaults(self) -> None:
        schema = MeterSpecSchema()
        assert schema.name == "ямб"
        assert schema.foot_count == 4

    def test_to_domain_returns_canonicalised_meter(self) -> None:
        schema = MeterSpecSchema(name="iamb", foot_count=5)
        spec = schema.to_domain()
        assert isinstance(spec, MeterSpec)
        assert spec.name == "ямб"  # canonicalised
        assert spec.foot_count == 5

    def test_from_domain_roundtrip(self) -> None:
        spec = MeterSpec(name="хорей", foot_count=3)
        schema = MeterSpecSchema.from_domain(spec)
        assert schema.to_domain() == spec

    def test_foot_count_below_min_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            MeterSpecSchema(foot_count=0)

    def test_foot_count_above_max_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            MeterSpecSchema(foot_count=11)


# ---------------------------------------------------------------------------
# RhymeSchemeSchema
# ---------------------------------------------------------------------------

class TestRhymeSchemeSchema:
    def test_default_is_abab(self) -> None:
        assert RhymeSchemeSchema().pattern == "ABAB"

    def test_to_domain_strict(self) -> None:
        schema = RhymeSchemeSchema(pattern="AABB")
        scheme = schema.to_domain()
        assert isinstance(scheme, RhymeScheme)
        assert scheme.pattern == "AABB"

    def test_from_domain_roundtrip(self) -> None:
        original = RhymeScheme(pattern="ABBA")
        schema = RhymeSchemeSchema.from_domain(original)
        assert schema.to_domain() == original

    def test_unknown_pattern_surfaces_domain_error_at_to_domain(self) -> None:
        # Schema accepts arbitrary strings at the Pydantic layer (no enum
        # constraint). The domain `RhymeScheme` constructor raises on
        # unknown patterns, so conversion fails there.
        schema = RhymeSchemeSchema(pattern="XYZW")
        with pytest.raises(Exception):  # UnsupportedConfigError
            schema.to_domain()


# ---------------------------------------------------------------------------
# PoemStructureSchema
# ---------------------------------------------------------------------------

class TestPoemStructureSchema:
    def test_defaults(self) -> None:
        s = PoemStructureSchema()
        assert s.stanza_count == 4
        assert s.lines_per_stanza == 4

    def test_to_domain_constructs_poem_structure(self) -> None:
        s = PoemStructureSchema(stanza_count=2, lines_per_stanza=4)
        ps = s.to_domain()
        assert isinstance(ps, PoemStructure)
        assert ps.stanza_count == 2
        assert ps.lines_per_stanza == 4
        assert ps.total_lines == 8

    def test_stanza_count_out_of_range(self) -> None:
        with pytest.raises(PydanticValidationError):
            PoemStructureSchema(stanza_count=0, lines_per_stanza=4)
        with pytest.raises(PydanticValidationError):
            PoemStructureSchema(stanza_count=11, lines_per_stanza=4)

    def test_lines_per_stanza_must_be_four(self) -> None:
        with pytest.raises(PydanticValidationError):
            PoemStructureSchema(stanza_count=4, lines_per_stanza=2)  # type: ignore[arg-type]
        with pytest.raises(PydanticValidationError):
            PoemStructureSchema(stanza_count=4, lines_per_stanza=6)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GenerationRequestSchema
# ---------------------------------------------------------------------------

class TestGenerationRequestSchema:
    def test_to_domain_bundles_every_field(self) -> None:
        schema = GenerationRequestSchema(
            theme="весна в лісі",
            meter=MeterSpecSchema(name="ямб", foot_count=4),
            rhyme=RhymeSchemeSchema(pattern="ABAB"),
            structure=PoemStructureSchema(stanza_count=2, lines_per_stanza=4),
            max_iterations=2,
            top_k=7,
            metric_examples_top_k=4,
        )
        req = schema.to_domain()
        assert req.theme == "весна в лісі"
        assert req.meter.name == "ямб"
        assert req.rhyme.pattern == "ABAB"
        assert req.structure.total_lines == 8
        assert req.max_iterations == 2
        assert req.top_k == 7
        assert req.metric_examples_top_k == 4

    def test_empty_theme_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            GenerationRequestSchema(theme="")

    def test_max_iterations_out_of_range(self) -> None:
        with pytest.raises(PydanticValidationError):
            GenerationRequestSchema(theme="весна", max_iterations=-1)
        with pytest.raises(PydanticValidationError):
            GenerationRequestSchema(theme="весна", max_iterations=4)

    def test_defaults_fill_nested_schemas(self) -> None:
        schema = GenerationRequestSchema(theme="мінімальний")
        req = schema.to_domain()
        assert req.meter.name == "ямб"
        assert req.rhyme.pattern == "ABAB"
        assert req.structure.stanza_count == 4


# ---------------------------------------------------------------------------
# ValidationRequestSchema
# ---------------------------------------------------------------------------

class TestValidationRequestSchema:
    def test_to_domain_returns_validation_request(self) -> None:
        schema = ValidationRequestSchema(
            poem_text="рядок один\nрядок два",
            meter=MeterSpecSchema(name="ямб", foot_count=4),
            rhyme=RhymeSchemeSchema(pattern="ABAB"),
        )
        req = schema.to_domain()
        assert req.poem_text.startswith("рядок")
        assert req.meter.name == "ямб"
        assert req.rhyme.pattern == "ABAB"

    def test_empty_poem_text_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            ValidationRequestSchema(poem_text="")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TestValidationResultSchemaFromStrings:
    def test_combines_meter_and_rhyme_feedback(self) -> None:
        v = ValidationResult(
            meter=MeterResult(ok=False, accuracy=0.5),
            rhyme=RhymeResult(ok=True, accuracy=1.0),
            iterations=2,
        )
        schema = ValidationResultSchema.from_strings(
            v, meter_msgs=["bad line 2"], rhyme_msgs=["no rhyme 3/4"],
        )
        assert schema.is_valid is False
        assert schema.iterations == 2
        assert schema.meter.ok is False
        assert schema.meter.accuracy == 0.5
        assert schema.meter.feedback == ["bad line 2"]
        assert schema.rhyme.ok is True
        assert schema.feedback == ["bad line 2", "no rhyme 3/4"]

    def test_empty_feedback_lists_permitted(self) -> None:
        v = ValidationResult(
            meter=MeterResult(ok=True, accuracy=1.0),
            rhyme=RhymeResult(ok=True, accuracy=1.0),
        )
        schema = ValidationResultSchema.from_strings(v, meter_msgs=[], rhyme_msgs=[])
        assert schema.is_valid is True
        assert schema.feedback == []


class TestGenerationResultSchemaFromStrings:
    def test_wraps_validation_schema_and_preserves_poem(self) -> None:
        v = ValidationResult(
            meter=MeterResult(ok=True, accuracy=1.0),
            rhyme=RhymeResult(ok=True, accuracy=1.0),
        )
        r = GenerationResult(poem="рядок 1\nрядок 2\n", validation=v)
        schema = GenerationResultSchema.from_strings(r, meter_msgs=[], rhyme_msgs=[])
        assert schema.poem == "рядок 1\nрядок 2\n"
        assert schema.validation.is_valid is True
        assert schema.iteration_history == []

    def test_exposes_iteration_history_for_frontend(self) -> None:
        # The web UI's "feedback iterations" panel needs the intermediate
        # drafts, not just the final poem — ensure the schema carries them.
        v = ValidationResult(
            meter=MeterResult(ok=True, accuracy=1.0),
            rhyme=RhymeResult(ok=True, accuracy=1.0),
            iterations=1,
        )
        history = (
            IterationSnapshot(
                iteration=0,
                poem="чернетка 0",
                meter_accuracy=0.5,
                rhyme_accuracy=1.0,
                feedback=("виправ рядок 2",),
                duration_sec=0.8,
            ),
            IterationSnapshot(
                iteration=1,
                poem="чернетка 1",
                meter_accuracy=1.0,
                rhyme_accuracy=1.0,
                feedback=(),
                duration_sec=28.9,
            ),
        )
        r = GenerationResult(
            poem="чернетка 1", validation=v, iteration_history=history,
        )
        schema = GenerationResultSchema.from_strings(r, meter_msgs=[], rhyme_msgs=[])
        assert len(schema.iteration_history) == 2
        first = schema.iteration_history[0]
        assert first.iteration == 0
        assert first.poem == "чернетка 0"
        assert first.meter_accuracy == 0.5
        assert first.feedback == ["виправ рядок 2"]
        assert first.duration_sec == 0.8
        assert schema.iteration_history[1].poem == "чернетка 1"


# ---------------------------------------------------------------------------
# Detection schemas
# ---------------------------------------------------------------------------

class TestDetectionRequestSchema:
    def test_empty_poem_text_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            DetectionRequestSchema(poem_text="")

    def test_sample_lines_default_is_none(self) -> None:
        schema = DetectionRequestSchema(poem_text="текст вірша")
        assert schema.sample_lines is None

    def test_sample_lines_out_of_range(self) -> None:
        with pytest.raises(PydanticValidationError):
            DetectionRequestSchema(poem_text="текст", sample_lines=1)
        with pytest.raises(PydanticValidationError):
            DetectionRequestSchema(poem_text="текст", sample_lines=15)


class TestDetectionResultSchema:
    def test_from_domain_both_detected(self) -> None:
        r = DetectionResult(
            meter=MeterDetection(meter="ямб", foot_count=4, accuracy=0.95),
            rhyme=RhymeDetection(scheme="ABAB", accuracy=0.9),
        )
        schema = DetectionResultSchema.from_domain(r)
        assert schema.is_detected is True
        assert schema.meter is not None
        assert schema.meter.meter == "ямб"
        assert schema.rhyme is not None
        assert schema.rhyme.scheme == "ABAB"

    def test_from_domain_nothing_detected(self) -> None:
        r = DetectionResult(meter=None, rhyme=None)
        schema = DetectionResultSchema.from_domain(r)
        assert schema.is_detected is False
        assert schema.meter is None
        assert schema.rhyme is None
