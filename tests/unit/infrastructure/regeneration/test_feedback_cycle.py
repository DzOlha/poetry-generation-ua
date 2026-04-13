"""Tests for `ValidationFeedbackCycle`."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.models import (
    MeterResult,
    MeterSpec,
    RhymeResult,
    RhymeScheme,
)
from src.domain.ports import (
    IFeedbackFormatter,
    IMeterValidator,
    IRhymeValidator,
)
from src.infrastructure.regeneration.feedback_cycle import ValidationFeedbackCycle


@dataclass
class _FakeMeterValidator(IMeterValidator):
    result: MeterResult
    calls: list[tuple[str, MeterSpec]]

    def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult:
        self.calls.append((poem_text, meter))
        return self.result


@dataclass
class _FakeRhymeValidator(IRhymeValidator):
    result: RhymeResult
    calls: list[tuple[str, RhymeScheme]]

    def validate(self, poem_text: str, scheme: RhymeScheme) -> RhymeResult:
        self.calls.append((poem_text, scheme))
        return self.result


class _CapturingFormatter(IFeedbackFormatter):
    def __init__(self) -> None:
        self.line_calls: list[LineFeedback] = []
        self.pair_calls: list[PairFeedback] = []

    def format_line(self, fb: LineFeedback) -> str:
        self.line_calls.append(fb)
        return f"LINE({fb.line_idx})"

    def format_pair(self, fb: PairFeedback) -> str:
        self.pair_calls.append(fb)
        return f"PAIR({fb.line_a_idx},{fb.line_b_idx})"


class TestValidationFeedbackCycle:
    def test_validates_and_formats(self) -> None:
        line_fb = LineFeedback(
            line_idx=0,
            meter_name="ямб",
            foot_count=4,
            expected_stresses=(2, 4),
            actual_stresses=(1, 4),
            total_syllables=4,
        )
        pair_fb = PairFeedback(
            line_a_idx=0, line_b_idx=2,
            scheme_pattern="ABAB",
            word_a="ліс", word_b="вітер",
            rhyme_part_a="is", rhyme_part_b="iter",
            score=0.2,
        )
        meter = _FakeMeterValidator(
            result=MeterResult(ok=False, accuracy=0.75, feedback=(line_fb,)),
            calls=[],
        )
        rhyme = _FakeRhymeValidator(
            result=RhymeResult(ok=False, accuracy=0.5, feedback=(pair_fb,)),
            calls=[],
        )
        formatter = _CapturingFormatter()
        cycle = ValidationFeedbackCycle(
            meter_validator=meter,
            rhyme_validator=rhyme,
            feedback_formatter=formatter,
        )
        outcome = cycle.run(
            poem_text="poem",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        )
        assert outcome.meter.accuracy == 0.75
        assert outcome.rhyme.accuracy == 0.5
        assert outcome.feedback_messages == ("LINE(0)", "PAIR(0,2)")
        assert len(meter.calls) == 1
        assert len(rhyme.calls) == 1
