"""Base class for meter validators — shared line-splitting + aggregation logic.

Validators delegate per-line analysis to their subclass via `_validate_line`
and let `LineMeterResult` describe itself polymorphically for feedback.
No more `isinstance(result, BSPMeterResult)` branches.
"""
from __future__ import annotations

from abc import abstractmethod

from src.domain.feedback import LineFeedback
from src.domain.models import LineMeterResult, MeterResult, MeterSpec
from src.domain.ports import (
    ILineFeedbackBuilder,
    IMeterValidator,
    IProsodyAnalyzer,
    ITextProcessor,
)


class BaseMeterValidator(IMeterValidator):
    """Abstract base providing shared line-splitting + aggregation logic.

    Args:
        prosody:              Injected prosody analyser.
        text_processor:       Injected text processor for line splitting.
        feedback_builder:     Injected builder for per-line `LineFeedback` DTOs.
        allowed_mismatches:   Maximum tolerated non-pyrrhic errors per line.
    """

    def __init__(
        self,
        prosody: IProsodyAnalyzer,
        text_processor: ITextProcessor,
        feedback_builder: ILineFeedbackBuilder,
        allowed_mismatches: int = 2,
    ) -> None:
        self._prosody = prosody
        self._text = text_processor
        self._feedback_builder = feedback_builder
        self.allowed_mismatches = allowed_mismatches

    def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult:
        lines = self._text.split_lines(poem_text)
        if not lines:
            return MeterResult(ok=False, accuracy=0.0)

        line_results = tuple(self._validate_line(ln, meter) for ln in lines)
        ok = all(r.ok for r in line_results)
        accuracy = sum(1 for r in line_results if r.ok) / len(line_results)
        feedback: tuple[LineFeedback, ...] = tuple(
            self._feedback_builder.build(i, meter, r)
            for i, r in enumerate(line_results)
            if not r.ok
        )
        return MeterResult(
            ok=ok,
            accuracy=accuracy,
            feedback=feedback,
            line_results=line_results,
        )

    @abstractmethod
    def _validate_line(self, line: str, meter: MeterSpec) -> LineMeterResult:
        """Validate a single line. Implemented by concrete subclasses."""
