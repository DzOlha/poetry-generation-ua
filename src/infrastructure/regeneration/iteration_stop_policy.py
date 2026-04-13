"""IIterationStopPolicy implementations.

Today we offer a simple "stop when max reached or both validators pass"
policy; the port lets future work add plateau / degradation detection
without touching the feedback iterator.
"""
from __future__ import annotations

from src.domain.evaluation import IterationRecord
from src.domain.models import MeterResult, RhymeResult
from src.domain.ports import IIterationStopPolicy


class MaxIterationsOrValidStopPolicy(IIterationStopPolicy):
    """Stops when both validators pass, or when `max_iterations` is reached."""

    def should_stop(
        self,
        iteration: int,
        max_iterations: int,
        meter_result: MeterResult,
        rhyme_result: RhymeResult,
        history: tuple[IterationRecord, ...],
    ) -> bool:
        if iteration > max_iterations:
            return True
        return meter_result.ok and rhyme_result.ok
