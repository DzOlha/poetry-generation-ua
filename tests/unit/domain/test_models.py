"""Unit tests for the value/command/result objects in src.domain.models."""
from __future__ import annotations

import pytest

from src.domain.errors import UnsupportedConfigError
from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    MeterResult,
    MeterSpec,
    PoemStructure,
    RhymeResult,
    RhymeScheme,
    ValidationResult,
)

# ===========================================================================
# MeterSpec
# ===========================================================================

class TestMeterSpec:
    def test_creates_with_valid_args(self):
        spec = MeterSpec(name="ямб", foot_count=4)
        assert spec.name == "ямб"
        assert spec.foot_count == 4

    def test_frozen_immutability(self):
        spec = MeterSpec(name="хорей", foot_count=3)
        with pytest.raises((AttributeError, TypeError)):
            spec.name = "ямб"  # type: ignore[misc]

    def test_equality_by_value(self):
        assert MeterSpec(name="ямб", foot_count=4) == MeterSpec(name="ямб", foot_count=4)

    def test_canonicalises_english_alias(self):
        # Construction accepts 'iamb' but canonicalises to the Ukrainian form.
        assert MeterSpec(name="iamb", foot_count=4).name == "ямб"

    def test_negative_foot_count_raises(self):
        with pytest.raises(UnsupportedConfigError):
            MeterSpec(name="ямб", foot_count=-1)

    def test_zero_foot_count_is_allowed(self):
        assert MeterSpec(name="ямб", foot_count=0).foot_count == 0


# ===========================================================================
# RhymeScheme
# ===========================================================================

class TestRhymeScheme:
    def test_creates_with_valid_pattern(self):
        assert RhymeScheme(pattern="ABAB").pattern == "ABAB"

    def test_normalises_to_uppercase(self):
        assert RhymeScheme(pattern="aabb").pattern == "AABB"

    def test_strips_whitespace(self):
        assert RhymeScheme(pattern="  ABBA  ").pattern == "ABBA"

    def test_as_enum_roundtrip(self):
        from src.domain.values import RhymePattern
        assert RhymeScheme("ABAB").as_enum == RhymePattern.ABAB


# ===========================================================================
# PoemStructure
# ===========================================================================

class TestPoemStructure:
    def test_total_lines(self):
        assert PoemStructure(3, 4).total_lines == 12

    def test_frozen(self):
        s = PoemStructure(2, 4)
        with pytest.raises((AttributeError, TypeError)):
            s.stanza_count = 3  # type: ignore[misc]


# ===========================================================================
# GenerationRequest
# ===========================================================================

class TestGenerationRequest:
    def test_creates_with_required_args(self):
        req = GenerationRequest(
            theme="весна",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
            structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
        )
        assert req.theme == "весна"
        assert req.structure.total_lines == 4

    def test_defaults(self):
        req = GenerationRequest(
            theme="тест",
            meter=MeterSpec("ямб", 4),
            rhyme=RhymeScheme("ABAB"),
            structure=PoemStructure(1, 4),
        )
        assert req.max_iterations == 3
        assert req.top_k == 5


# ===========================================================================
# ValidationResult
# ===========================================================================

class TestValidationResult:
    def _valid_result(self, **kwargs) -> ValidationResult:
        return ValidationResult(
            meter=kwargs.get("meter", MeterResult(ok=True, accuracy=1.0)),
            rhyme=kwargs.get("rhyme", RhymeResult(ok=True, accuracy=1.0)),
            iterations=kwargs.get("iterations", 0),
        )

    def test_is_valid_both_ok(self):
        assert self._valid_result().is_valid is True

    def test_is_valid_meter_fails(self):
        line_fb = LineFeedback(
            line_idx=0, meter_name="ямб", foot_count=4,
            expected_stresses=(2, 4), actual_stresses=(1,), total_syllables=4,
        )
        r = self._valid_result(meter=MeterResult(ok=False, accuracy=0.5, feedback=(line_fb,)))
        assert r.is_valid is False

    def test_is_valid_rhyme_fails(self):
        pair_fb = PairFeedback(
            line_a_idx=0, line_b_idx=1, scheme_pattern="AABB",
            word_a="a", word_b="b", rhyme_part_a="a", rhyme_part_b="b", score=0.1,
        )
        r = self._valid_result(rhyme=RhymeResult(ok=False, accuracy=0.0, feedback=(pair_fb,)))
        assert r.is_valid is False

    def test_feedback_combines_meter_and_rhyme(self):
        line_fb = LineFeedback(
            line_idx=0, meter_name="ямб", foot_count=4,
            expected_stresses=(2,), actual_stresses=(1,), total_syllables=4,
        )
        pair_fb = PairFeedback(
            line_a_idx=0, line_b_idx=1, scheme_pattern="AABB",
            word_a="a", word_b="b", rhyme_part_a="a", rhyme_part_b="b", score=0.0,
        )
        r = ValidationResult(
            meter=MeterResult(ok=False, accuracy=0.5, feedback=(line_fb,)),
            rhyme=RhymeResult(ok=False, accuracy=0.5, feedback=(pair_fb,)),
        )
        combined = r.feedback
        assert line_fb in combined
        assert pair_fb in combined


# ===========================================================================
# GenerationResult
# ===========================================================================

class TestGenerationResult:
    def test_bundles_poem_and_validation(self):
        validation = ValidationResult(
            meter=MeterResult(ok=True, accuracy=1.0),
            rhyme=RhymeResult(ok=True, accuracy=1.0),
        )
        result = GenerationResult(poem="рядок один\nрядок два\n", validation=validation)
        assert result.validation is validation


# ===========================================================================
# IFeedbackFormatter concatenation behaviour
# ===========================================================================

class TestFeedbackFormatterProtocol:
    """The tuple-ordering contract between MeterResult/RhymeResult and IFeedbackFormatter."""

    def test_format_all_orders_meter_first_then_rhyme(self, feedback_formatter):
        line_fb = LineFeedback(
            line_idx=0, meter_name="ямб", foot_count=4,
            expected_stresses=(2,), actual_stresses=(1,), total_syllables=4,
        )
        pair_fb = PairFeedback(
            line_a_idx=0, line_b_idx=1, scheme_pattern="AABB",
            word_a="a", word_b="b", rhyme_part_a="a", rhyme_part_b="b", score=0.0,
        )
        from src.domain.ports import format_all_feedback
        msgs = format_all_feedback(feedback_formatter, (line_fb,), (pair_fb,))
        assert len(msgs) == 2
        assert "Line 1" in msgs[0]
        assert "Lines 1 and 2" in msgs[1]
