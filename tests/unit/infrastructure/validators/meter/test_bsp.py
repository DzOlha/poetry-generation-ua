"""Unit tests for BSP core math, BSPMeterValidator, and PatternMeterValidator."""
from __future__ import annotations

import pytest

from src.domain.models import LineMeterResult, MeterSpec
from src.infrastructure.meter import UkrainianMeterTemplateProvider
from src.infrastructure.text import UkrainianTextProcessor
from src.infrastructure.validators.meter.bsp_algorithm import (
    BSPAlgorithm,
    BSPIssue,
)
from src.infrastructure.validators.meter.bsp_validator import BSPMeterValidator
from src.infrastructure.validators.meter.feedback_builder import DefaultLineFeedbackBuilder
from src.infrastructure.validators.meter.pattern_validator import PatternMeterValidator
from src.infrastructure.validators.meter.prosody import UkrainianProsodyAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_bsp = BSPAlgorithm()


class TestBuildDifferencePyramid:
    def test_empty_returns_empty(self):
        assert _bsp.build_difference_pyramid([]) == []

    def test_single_element(self):
        assert _bsp.build_difference_pyramid([1]) == [[1]]

    def test_two_elements(self):
        result = _bsp.build_difference_pyramid([0, 1])
        assert result[0] == [0, 1]
        assert result[1] == [1]

    def test_iamb_stress_sequence(self):
        result = _bsp.build_difference_pyramid([0, 1, 0, 1])
        assert result[0] == [0, 1, 0, 1]
        assert result[1] == [1, -1, 1]
        assert result[2] == [-2, 2]

    def test_uniform_sequence(self):
        result = _bsp.build_difference_pyramid([1, 1, 1])
        assert result[1] == [0, 0]
        assert result[2] == [0]

    def test_pyramid_depth(self):
        seq = [0, 1, 0, 1, 0, 1]
        assert len(_bsp.build_difference_pyramid(seq)) == len(seq)


class TestBuildSumPyramid:
    def test_empty_returns_empty(self):
        assert _bsp.build_sum_pyramid([]) == []

    def test_single_element(self):
        assert _bsp.build_sum_pyramid([1]) == [[1]]

    def test_two_elements(self):
        result = _bsp.build_sum_pyramid([0, 1])
        assert result[0] == [0, 1]
        assert result[1] == [1]

    def test_iamb_first_row(self):
        result = _bsp.build_sum_pyramid([0, 1, 0, 1])
        assert result[0] == [0, 1, 0, 1]
        assert result[1] == [1, 1, 1]

    def test_top_value_is_total_sum(self):
        assert len(_bsp.build_sum_pyramid([1, 0, 1, 0, 1])[-1]) == 1


class TestAlternationScore:
    def test_perfect_iamb_scores_high(self):
        d = _bsp.build_difference_pyramid([0, 1, 0, 1])
        assert _bsp.alternation_score(d, [0, 1, 0, 1]) >= 0.9

    def test_all_wrong_scores_zero(self):
        d = _bsp.build_difference_pyramid([0, 0, 0, 0])
        assert _bsp.alternation_score(d, [0, 1, 0, 1]) < 0.5

    def test_empty_pyramid_returns_zero(self):
        assert _bsp.alternation_score([], [0, 1]) == 0.0

    def test_single_row_pyramid_returns_zero(self):
        assert _bsp.alternation_score([[0, 1]], [0, 1]) == 0.0


class TestVariationTolerance:
    def test_no_zeros_scores_one(self):
        assert _bsp.variation_tolerance([[], [1, -1, 1, -1]]) == 1.0

    def test_all_zeros_penalised(self):
        assert _bsp.variation_tolerance([[], [0, 0, 0, 0]]) < 0.5

    def test_few_zeros_acceptable(self):
        assert _bsp.variation_tolerance([[], [1, 0, -1, 1]]) == 1.0

    def test_shallow_pyramid_returns_one(self):
        assert _bsp.variation_tolerance([]) == 1.0
        assert _bsp.variation_tolerance([[1, 0, 1]]) == 1.0


class TestGlobalStability:
    def test_shallow_pyramid_returns_one(self):
        d = _bsp.build_difference_pyramid([0, 1])
        assert _bsp.global_stability(d) == 1.0

    def test_periodic_signal_is_stable(self):
        d = _bsp.build_difference_pyramid([0, 1, 0, 1, 0, 1, 0, 1])
        assert 0.0 <= _bsp.global_stability(d) <= 1.0

    def test_returns_float_in_range(self):
        for seq in ([0, 0, 0, 0], [1, 1, 1, 1], [0, 1, 0, 1]):
            d = _bsp.build_difference_pyramid(seq)
            assert 0.0 <= _bsp.global_stability(d) <= 1.0


class TestBalanceScore:
    def test_half_stressed_scores_one(self):
        assert _bsp.balance_score(_bsp.build_sum_pyramid([0, 1, 0, 1])) == 1.0

    def test_all_stressed_penalised(self):
        assert _bsp.balance_score(_bsp.build_sum_pyramid([1, 1, 1, 1])) < 1.0

    def test_empty_returns_zero(self):
        assert _bsp.balance_score([]) == 0.0


class TestComputeBspScore:
    def test_perfect_match_scores_high(self):
        seq = [0, 1, 0, 1, 0, 1, 0, 1]
        assert _bsp.compute_score(seq, seq) >= 0.8

    def test_empty_inputs_return_zero(self):
        assert _bsp.compute_score([], [0, 1]) == 0.0
        assert _bsp.compute_score([0, 1], []) == 0.0

    def test_inverted_pattern_scores_low(self):
        assert _bsp.compute_score([1, 0, 1, 0], [0, 1, 0, 1]) < 0.5

    def test_score_bounded(self):
        for _ in range(5):
            assert 0.0 <= _bsp.compute_score([0, 1, 0, 1], [0, 1, 0, 1]) <= 1.0


class TestDetectBspErrors:
    def test_no_issues_on_perfect_match(self):
        seq = [0, 1, 0, 1]
        flags = [(False, False)] * 4
        assert _bsp.detect_errors(seq, seq, flags) == []

    def test_stress_missing_reported(self):
        issues = _bsp.detect_errors(
            [0, 0, 0, 1], [0, 1, 0, 1], [(False, False)] * 4,
        )
        assert "stress_missing" in [i.type for i in issues]

    def test_stress_overflow_reported(self):
        issues = _bsp.detect_errors(
            [1, 1, 0, 1], [0, 1, 0, 1], [(False, False)] * 4,
        )
        assert "stress_overflow" in [i.type for i in issues]

    def test_consecutive_stressed_rhythm_break(self):
        issues = _bsp.detect_errors(
            [1, 1, 0, 1], [0, 1, 0, 1], [(False, False)] * 4,
        )
        assert "rhythm_break" in [i.type for i in issues]

    def test_pyrrhic_on_weak_word_tolerated(self):
        issues = _bsp.detect_errors(
            [0, 0], [0, 1], [(False, False), (True, True)],
        )
        assert all(i.type != "stress_missing" for i in issues)

    def test_spondee_on_mono_word_tolerated(self):
        issues = _bsp.detect_errors(
            [1, 1], [0, 1], [(True, False), (False, False)],
        )
        assert all(i.type != "stress_overflow" for i in issues)

    def test_issue_has_required_fields(self):
        issues = _bsp.detect_errors(
            [0, 0, 0, 0], [0, 1, 0, 1], [(False, False)] * 4,
        )
        for iss in issues:
            assert isinstance(iss, BSPIssue)
            assert iss.type in ("stress_missing", "stress_overflow", "rhythm_break")


class TestDetectClausula:
    def test_masculine_last_stressed(self):
        assert _bsp.detect_clausula([0, 1, 0, 1]) == "masculine"

    def test_feminine_penultimate(self):
        assert _bsp.detect_clausula([0, 1, 0, 1, 0]) == "feminine"

    def test_dactylic_antepenultimate(self):
        assert _bsp.detect_clausula([0, 1, 0, 1, 0, 0]) == "dactylic"

    def test_hyperdactylic_far_from_end(self):
        assert _bsp.detect_clausula([0, 1, 0, 0, 0]) == "hyperdactylic"

    def test_empty_returns_unknown(self):
        assert _bsp.detect_clausula([]) == "unknown"

    def test_no_stress_returns_unknown(self):
        assert _bsp.detect_clausula([0, 0, 0]) == "unknown"


class TestBSPAlgorithm:
    def test_custom_weights_accepted(self):
        algo = BSPAlgorithm(alternation_weight=0.7, variation_weight=0.1,
                            stability_weight=0.1, balance_weight=0.1)
        assert 0.0 <= algo.compute_score([0, 1, 0, 1], [0, 1, 0, 1]) <= 1.0


class TestBSPAnnotation:
    def test_bsp_annotation_in_result(self):
        """BSP validator produces a LineMeterResult with an annotation string."""
        result = LineMeterResult(
            ok=True,
            expected_stresses=(2, 4),
            actual_stresses=(2, 4),
            error_positions=(),
            total_syllables=4,
            annotation=" (BSP score: 0.90)",
        )
        assert isinstance(result, LineMeterResult)
        assert "BSP score" in result.annotation

    def test_annotation_includes_first_issue(self):
        result = LineMeterResult(
            ok=False,
            expected_stresses=(2, 4),
            actual_stresses=(1, 4),
            error_positions=(2,),
            total_syllables=4,
            annotation=" (BSP score: 0.42) — some message",
        )
        assert "0.42" in result.annotation
        assert "some message" in result.annotation


class TestBSPMeterValidator:
    @pytest.fixture
    def validator(
        self,
        prosody_analyzer: UkrainianProsodyAnalyzer,
    ) -> BSPMeterValidator:
        return BSPMeterValidator(
            prosody=prosody_analyzer,
            text_processor=UkrainianTextProcessor(),
            feedback_builder=DefaultLineFeedbackBuilder(
                template_provider=UkrainianMeterTemplateProvider(),
            ),
            bsp_algorithm=BSPAlgorithm(),
            score_threshold=0.6,
        )

    def test_validate_line_returns_line_meter_result(self, validator):
        result = validator._validate_line("Весна прийшла у ліс", MeterSpec("ямб", 4))
        assert isinstance(result, LineMeterResult)

    def test_result_has_bsp_annotation(self, validator):
        result = validator._validate_line("Весна прийшла у ліс", MeterSpec("ямб", 4))
        assert "BSP score" in result.annotation

    def test_validate_returns_line_results(self, validator):
        poem = "Весна прийшла у ліс зелений,\nІ спів пташок в гіллі бринить.\n"
        meter_result = validator.validate(poem, MeterSpec("ямб", 4))
        assert len(meter_result.line_results) == 2

    def test_empty_poem_returns_not_ok(self, validator):
        # Empty poems must not silently pass: there's nothing to validate.
        assert validator.validate("", MeterSpec("ямб", 4)).ok is False

    def test_shevchenko_iamb4_high_accuracy(self, validator):
        poem = (
            "Реве та стогне Дніпр широкий,\n"
            "Сердитий вітер завива,\n"
            "Додолу верби гне високі,\n"
            "Горами хвилю підійма."
        )
        result = validator.validate(poem, MeterSpec("ямб", 4))
        assert sum(1 for r in result.line_results if r.ok) >= 2

    def test_custom_bsp_algorithm_injected(self, prosody_analyzer):
        custom_bsp = BSPAlgorithm(
            alternation_weight=0.8, variation_weight=0.1,
            stability_weight=0.05, balance_weight=0.05,
        )
        validator = BSPMeterValidator(
            prosody=prosody_analyzer,
            text_processor=UkrainianTextProcessor(),
            feedback_builder=DefaultLineFeedbackBuilder(
                template_provider=UkrainianMeterTemplateProvider(),
            ),
            bsp_algorithm=custom_bsp,
        )
        result = validator._validate_line("Весна прийшла у ліс", MeterSpec("ямб", 4))
        assert isinstance(result, LineMeterResult)


class TestPatternMeterValidator:
    @pytest.fixture
    def validator(
        self,
        prosody_analyzer: UkrainianProsodyAnalyzer,
    ) -> PatternMeterValidator:
        return PatternMeterValidator(
            prosody=prosody_analyzer,
            text_processor=UkrainianTextProcessor(),
            feedback_builder=DefaultLineFeedbackBuilder(
                template_provider=UkrainianMeterTemplateProvider(),
            ),
        )

    def test_validate_line_returns_line_meter_result(self, validator):
        result = validator._validate_line("Весна прийшла у ліс", MeterSpec("ямб", 4))
        assert isinstance(result, LineMeterResult)

    def test_shevchenko_iamb4(self, validator):
        poem = (
            "Реве та стогне Дніпр широкий,\n"
            "Сердитий вітер завива,\n"
            "Додолу верби гне високі,\n"
            "Горами хвилю підійма."
        )
        result = validator.validate(poem, MeterSpec("ямб", 4))
        assert sum(1 for r in result.line_results if r.ok) >= 2
