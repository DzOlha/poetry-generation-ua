"""Markdown reporter — IReporter façade composing focused formatters.

After the architectural audit, the four concerns this class used to
mix (table layout, trace rendering, cost arithmetic, document assembly)
each live in their own helper:

  - ``TableFormatter``           — summary-table row layout
  - ``TraceFormatter``           — per-trace text block
  - ``CostCalculator``           — per-call USD arithmetic
  - ``MarkdownDocumentBuilder``  — top-level section ordering

The reporter wires them together and exposes the original ``IReporter``
contract so existing call sites keep working unchanged.
"""
from __future__ import annotations

from src.domain.evaluation import EvaluationSummary, PipelineTrace
from src.domain.ports import IReporter
from src.infrastructure.reporting.cost_calculator import CostCalculator
from src.infrastructure.reporting.markdown_document_builder import (
    MarkdownDocumentBuilder,
)
from src.infrastructure.reporting.table_formatter import TableFormatter
from src.infrastructure.reporting.trace_formatter import TraceFormatter


class MarkdownReporter(IReporter):
    """IReporter that renders evaluation results as Markdown / plain text."""

    def __init__(
        self,
        *,
        scenario_name_width: int = 20,
        error_width: int = 30,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        config_descriptions: dict[str, str] | None = None,
        input_price_per_m: float = 0.0,
        output_price_per_m: float = 0.0,
    ) -> None:
        config_desc_tuple = tuple((config_descriptions or {}).items())
        self._table = TableFormatter(
            scenario_name_width=scenario_name_width,
            error_width=error_width,
            config_descriptions=config_desc_tuple,
        )
        self._trace = TraceFormatter(
            cost_calculator=CostCalculator(
                input_price_per_m=input_price_per_m,
                output_price_per_m=output_price_per_m,
            ),
        )
        self._document = MarkdownDocumentBuilder(
            table_formatter=self._table,
            trace_formatter=self._trace,
            config_descriptions=config_desc_tuple,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

    # ------------------------------------------------------------------
    # IReporter
    # ------------------------------------------------------------------

    def format_summary_table(self, summaries: list[EvaluationSummary]) -> str:
        return self._table.format_summary(summaries)

    def format_trace_detail(self, trace: PipelineTrace) -> str:
        return self._trace.format_trace(trace)

    def format_markdown_report(
        self,
        summaries: list[EvaluationSummary],
        traces: list[PipelineTrace],
    ) -> str:
        return self._document.build(summaries, traces)
