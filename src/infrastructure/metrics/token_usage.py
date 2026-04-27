"""Token-usage and estimated-cost metric calculators.

Each LLM call during a run records `input_tokens` and `output_tokens` on
its `IterationRecord` via `ILLMCallRecorder`. These calculators collapse
the per-iteration counts into run-level totals that downstream code
(BatchEvaluationService → CSV → analyzer → web) can display as headline
cost metrics alongside meter/rhyme accuracy.

`EstimatedCostCalculator` is price-aware — it takes Gemini's per-million
input/output prices via constructor (wired from `AppConfig`). Prices are
stored as "USD per 1M tokens" because that is how every public provider
publishes them, avoiding floating-point precision traps from tiny
per-token fractions.
"""
from __future__ import annotations

from src.domain.ports import EvaluationContext, IMetricCalculator


class InputTokensCalculator(IMetricCalculator):
    """Sum of input tokens across all iterations in the run."""

    @property
    def name(self) -> str:
        return "input_tokens"

    def calculate(self, context: EvaluationContext) -> float:
        return float(sum(it.input_tokens for it in context.iterations))


class OutputTokensCalculator(IMetricCalculator):
    """Sum of output tokens across all iterations (includes reasoning tokens)."""

    @property
    def name(self) -> str:
        return "output_tokens"

    def calculate(self, context: EvaluationContext) -> float:
        return float(sum(it.output_tokens for it in context.iterations))


class TotalTokensCalculator(IMetricCalculator):
    """Input + output tokens for the full run."""

    @property
    def name(self) -> str:
        return "total_tokens"

    def calculate(self, context: EvaluationContext) -> float:
        return float(sum(
            it.input_tokens + it.output_tokens for it in context.iterations
        ))


class EstimatedCostCalculator(IMetricCalculator):
    """USD cost estimate from token usage and tier prices.

    `input_price_per_m` / `output_price_per_m` are USD per 1 000 000 tokens
    (Gemini's published units). The result is "estimated" because it
    assumes every token is billed at the base tier (no cache hits, no
    premium context tier — Gemini 3.1 Pro for example charges more above
    200K context; a pilot run stays well below that threshold).
    """

    def __init__(self, input_price_per_m: float, output_price_per_m: float) -> None:
        self._input_price_per_m = float(input_price_per_m)
        self._output_price_per_m = float(output_price_per_m)

    @property
    def name(self) -> str:
        return "estimated_cost_usd"

    def calculate(self, context: EvaluationContext) -> float:
        input_tokens = sum(it.input_tokens for it in context.iterations)
        output_tokens = sum(it.output_tokens for it in context.iterations)
        return (
            input_tokens * self._input_price_per_m / 1_000_000.0
            + output_tokens * self._output_price_per_m / 1_000_000.0
        )
