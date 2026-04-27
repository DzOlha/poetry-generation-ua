"""LLM-call cost arithmetic — extracted from `MarkdownReporter`.

A small value object holds the per-million-token tier prices; instances
are pure (no I/O, no mutation) so they can be reused across reporters
and unit-tested in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostCalculator:
    """USD pricing helper for ``input_tokens / output_tokens`` pairs."""

    input_price_per_m: float = 0.0
    output_price_per_m: float = 0.0

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        """Return USD cost for one LLM call given tier prices per million."""
        return (
            input_tokens * self.input_price_per_m / 1_000_000.0
            + output_tokens * self.output_price_per_m / 1_000_000.0
        )
