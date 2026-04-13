"""`IFeedbackCycle` implementation — validates a poem and renders feedback.

Encapsulates `(meter validator, rhyme validator, feedback formatter)` as a
single unit so `ValidatingFeedbackIterator` depends on one collaborator for
the whole validate-and-format step instead of three.
"""
from __future__ import annotations

from src.domain.models import MeterSpec, RhymeScheme
from src.domain.ports import (
    FeedbackCycleOutcome,
    IFeedbackCycle,
    IFeedbackFormatter,
    IMeterValidator,
    IRhymeValidator,
    format_all_feedback,
)


class ValidationFeedbackCycle(IFeedbackCycle):
    """Runs meter + rhyme validators and formats their combined feedback."""

    def __init__(
        self,
        meter_validator: IMeterValidator,
        rhyme_validator: IRhymeValidator,
        feedback_formatter: IFeedbackFormatter,
    ) -> None:
        self._meter = meter_validator
        self._rhyme = rhyme_validator
        self._formatter = feedback_formatter

    def run(
        self,
        poem_text: str,
        meter: MeterSpec,
        rhyme: RhymeScheme,
    ) -> FeedbackCycleOutcome:
        meter_result = self._meter.validate(poem_text, meter)
        rhyme_result = self._rhyme.validate(poem_text, rhyme)
        messages = tuple(
            format_all_feedback(self._formatter, meter_result.feedback, rhyme_result.feedback),
        )
        return FeedbackCycleOutcome(
            meter=meter_result,
            rhyme=rhyme_result,
            feedback_messages=messages,
        )
