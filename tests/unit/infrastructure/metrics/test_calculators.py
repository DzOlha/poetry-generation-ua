"""Tests for the metric calculators."""
from __future__ import annotations

from src.domain.evaluation import IterationRecord
from src.domain.models import MeterSpec, RhymeScheme
from src.domain.ports import EvaluationContext, IMeterValidator, IRhymeValidator
from src.infrastructure.metrics import (
    FeedbackIterationsCalculator,
    LineCountCalculator,
    MeterAccuracyCalculator,
    MeterImprovementCalculator,
    RegenerationSuccessCalculator,
    RhymeAccuracyCalculator,
    RhymeImprovementCalculator,
)


def _context(poem: str, meter: str = "ямб", foot_count: int = 4, scheme: str = "ABAB") -> EvaluationContext:
    return EvaluationContext(
        poem_text=poem,
        meter=MeterSpec(name=meter, foot_count=foot_count),
        rhyme=RhymeScheme(pattern=scheme),
    )


def _context_with_iterations(
    poem: str,
    iterations: list[IterationRecord],
    meter: str = "ямб",
    foot_count: int = 4,
    scheme: str = "ABAB",
) -> EvaluationContext:
    return EvaluationContext(
        poem_text=poem,
        meter=MeterSpec(name=meter, foot_count=foot_count),
        rhyme=RhymeScheme(pattern=scheme),
        iterations=iterations,
    )


class TestMeterAccuracyCalculator:
    def test_forwards_actual_validator_score(self, meter_validator: IMeterValidator):
        # The calculator must return *exactly* what the validator computes
        # for the given (poem, meter). Type+bounds checks would pass even
        # for a broken implementation that always returns 0.5 — this test
        # pins down the forwarding contract.
        poem = (
            "Реве та стогне Дніпр широкий,\n"
            "Сердитий вітер завива,\n"
            "Додолу верби гне високі,\n"
            "Горами хвилю підійма.\n"
        )
        meter = MeterSpec(name="ямб", foot_count=4)
        expected = meter_validator.validate(poem, meter).accuracy
        calc = MeterAccuracyCalculator(meter_validator=meter_validator)
        assert calc.calculate(_context(poem)) == expected

    def test_calculates_partial_accuracy_for_partially_passing_poem(
        self, meter_validator: IMeterValidator,
    ):
        # The classical Shevchenko quatrain is fully iambic by hand,
        # but our stress resolver mis-stresses a couple of words
        # (`широкий, високі`) so empirically only 2/4 lines validate.
        # The point is: the calculator must return that real fractional
        # score, not 0.0 or 1.0. Pinning to 0.5 catches both:
        #   - regression to "all-or-nothing" scoring (would return 0.0/1.0)
        #   - regression to constant returns (e.g. always 1.0)
        poem = (
            "Реве та стогне Дніпр широкий,\n"
            "Сердитий вітер завива,\n"
            "Додолу верби гне високі,\n"
            "Горами хвилю підійма.\n"
        )
        calc = MeterAccuracyCalculator(meter_validator=meter_validator)
        assert calc.calculate(_context(poem)) == 0.5

    def test_empty_poem_fails_validation(self, meter_validator: IMeterValidator):
        # Empty poems intentionally fail: there is nothing to validate.
        calc = MeterAccuracyCalculator(meter_validator=meter_validator)
        assert calc.calculate(_context("")) == 0.0

    def test_name(self, meter_validator):
        assert MeterAccuracyCalculator(meter_validator=meter_validator).name == "meter_accuracy"


class TestRhymeAccuracyCalculator:
    def test_forwards_actual_validator_score(self, rhyme_validator: IRhymeValidator):
        # Same forwarding-contract pin-down as the meter calculator.
        poem = "ліс\nвіс\nріс\nніс\n"
        rhyme = RhymeScheme(pattern="AABB")
        expected = rhyme_validator.validate(poem, rhyme).accuracy
        calc = RhymeAccuracyCalculator(rhyme_validator=rhyme_validator)
        assert calc.calculate(_context(poem, scheme="AABB")) == expected

    def test_perfect_rhymes_score_one(self, rhyme_validator: IRhymeValidator):
        # 4 single-syllable words sharing the same stressed vowel `i` and
        # consonant `s`. AABB scheme → both pairs (1-2, 3-4) must rhyme.
        calc = RhymeAccuracyCalculator(rhyme_validator=rhyme_validator)
        assert calc.calculate(_context("ліс\nвіс\nріс\nніс\n", scheme="AABB")) == 1.0

    def test_empty_poem(self, rhyme_validator: IRhymeValidator):
        calc = RhymeAccuracyCalculator(rhyme_validator=rhyme_validator)
        assert calc.calculate(_context("")) == 1.0

    def test_name(self, rhyme_validator):
        assert RhymeAccuracyCalculator(rhyme_validator=rhyme_validator).name == "rhyme_accuracy"


class TestRegenerationSuccessCalculator:
    def test_empty_iterations_returns_zero(self):
        calc = RegenerationSuccessCalculator()
        assert calc.calculate(_context("")) == 0.0

    def test_single_iteration_returns_zero(self):
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.5, rhyme_accuracy=0.5, feedback=()),
        ])
        assert RegenerationSuccessCalculator().calculate(ctx) == 0.0

    def test_improvement_positive(self):
        # initial violations = 0.7 + 0.7 = 1.4;  final = 0.1 + 0.1 = 0.2.
        # coverage = 1 - 0.2/1.4 ≈ 0.857.
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.3, rhyme_accuracy=0.3, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=0.9, rhyme_accuracy=0.9, feedback=()),
        ])
        delta = RegenerationSuccessCalculator().calculate(ctx)
        assert 0.85 < delta < 0.86

    def test_full_fix_of_single_axis_with_other_already_perfect(self):
        # Regression against the old raw-delta formula: the rhyme axis is
        # already at the ceiling, so only the meter axis can improve — the
        # fix fully resolved the initial violation budget and the metric
        # must report 100%, not 50%.
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.0, rhyme_accuracy=1.0, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=1.0, rhyme_accuracy=1.0, feedback=()),
        ])
        assert RegenerationSuccessCalculator().calculate(ctx) == 1.0

    def test_initial_already_perfect_returns_full_success(self):
        # No violation budget to consume — regeneration had nothing to fix
        # and nothing broke, so return 1.0 (vacuously successful).
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=1.0, rhyme_accuracy=1.0, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=1.0, rhyme_accuracy=1.0, feedback=()),
        ])
        assert RegenerationSuccessCalculator().calculate(ctx) == 1.0

    def test_degradation_returned_as_negative(self):
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.9, rhyme_accuracy=0.9, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=0.3, rhyme_accuracy=0.3, feedback=()),
        ])
        delta = RegenerationSuccessCalculator().calculate(ctx)
        assert delta < 0.0


# ---------------------------------------------------------------------------
# Edge-case tests for calculators
# ---------------------------------------------------------------------------


class TestLineCountCalculator:
    def test_empty_poem_returns_zero(self):
        calc = LineCountCalculator()
        assert calc.calculate(_context("")) == 0

    def test_single_line(self):
        calc = LineCountCalculator()
        assert calc.calculate(_context("одна лінійка")) == 1

    def test_multiline(self):
        calc = LineCountCalculator()
        assert calc.calculate(_context(
            "рядок перший\nрядок другий\nрядок третій\n",
        )) == 3

    def test_whitespace_only(self):
        calc = LineCountCalculator()
        assert calc.calculate(_context("   \n  \n")) == 0

    def test_name(self):
        assert LineCountCalculator().name == "num_lines"


class TestFeedbackIterationsCalculator:
    def test_no_iterations_returns_zero(self):
        calc = FeedbackIterationsCalculator()
        assert calc.calculate(_context("")) == 0

    def test_counts_iterations(self):
        calc = FeedbackIterationsCalculator()
        ctx = _context_with_iterations("poem", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.5, rhyme_accuracy=0.5, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=0.8, rhyme_accuracy=0.8, feedback=()),
            IterationRecord(iteration=2, poem_text="", meter_accuracy=0.9, rhyme_accuracy=0.9, feedback=()),
        ])
        assert calc.calculate(ctx) == 2  # excludes the initial generation

    def test_name(self):
        assert FeedbackIterationsCalculator().name == "feedback_iterations"


class TestMeterImprovementCalculator:
    def test_no_iterations_returns_zero(self):
        calc = MeterImprovementCalculator()
        assert calc.calculate(_context("")) == 0.0

    def test_single_iteration_returns_zero(self):
        calc = MeterImprovementCalculator()
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.5, rhyme_accuracy=0.5, feedback=()),
        ])
        assert calc.calculate(ctx) == 0.0

    def test_improvement_returns_positive(self):
        calc = MeterImprovementCalculator()
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.3, rhyme_accuracy=0.5, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=0.8, rhyme_accuracy=0.5, feedback=()),
        ])
        delta = calc.calculate(ctx)
        assert delta > 0.0
        assert abs(delta - 0.5) < 0.01


class TestRhymeImprovementCalculator:
    def test_no_iterations_returns_zero(self):
        calc = RhymeImprovementCalculator()
        assert calc.calculate(_context("")) == 0.0

    def test_improvement_returns_positive(self):
        calc = RhymeImprovementCalculator()
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.5, rhyme_accuracy=0.2, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=0.5, rhyme_accuracy=0.9, feedback=()),
        ])
        delta = calc.calculate(ctx)
        assert delta > 0.0
        assert abs(delta - 0.7) < 0.01
