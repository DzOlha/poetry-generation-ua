"""Line count metric — how many non-empty lines the final poem has."""
from __future__ import annotations

from src.domain.models import Poem
from src.domain.ports import EvaluationContext, IMetricCalculator


class LineCountCalculator(IMetricCalculator):
    """Returns the number of non-empty lines in the generated poem."""

    @property
    def name(self) -> str:
        return "num_lines"

    def calculate(self, context: EvaluationContext) -> float:
        return float(Poem.from_text(context.poem_text).line_count)
