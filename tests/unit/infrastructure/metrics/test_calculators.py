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
    def test_returns_float(self, meter_validator: IMeterValidator):
        calc = MeterAccuracyCalculator(meter_validator=meter_validator)
        poem = "Весна прийшла у ліс зелений,\nДе тінь і світло гомонить.\n"
        acc = calc.calculate(_context(poem))
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

    def test_empty_poem_fails_validation(self, meter_validator: IMeterValidator):
        # Empty poems intentionally fail: there is nothing to validate.
        calc = MeterAccuracyCalculator(meter_validator=meter_validator)
        assert calc.calculate(_context("")) == 0.0

    def test_name(self, meter_validator):
        assert MeterAccuracyCalculator(meter_validator=meter_validator).name == "meter_accuracy"


class TestRhymeAccuracyCalculator:
    def test_returns_float(self, rhyme_validator: IRhymeValidator):
        calc = RhymeAccuracyCalculator(rhyme_validator=rhyme_validator)
        acc = calc.calculate(_context("ліс\nвіс\nріс\nніс\n", scheme="AABB"))
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

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
        ctx = _context_with_iterations("", [
            IterationRecord(iteration=0, poem_text="", meter_accuracy=0.3, rhyme_accuracy=0.3, feedback=()),
            IterationRecord(iteration=1, poem_text="", meter_accuracy=0.9, rhyme_accuracy=0.9, feedback=()),
        ])
        delta = RegenerationSuccessCalculator().calculate(ctx)
        assert 0.55 < delta < 0.65  # ~0.6

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
