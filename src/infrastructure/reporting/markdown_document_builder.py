"""Markdown document assembler — extracted from ``MarkdownReporter``.

Stitches the summary table, aggregate sections, token/cost block, and
trace details into a single Markdown document. Composes the table and
trace formatters; owns no formatting logic of its own beyond the
top-level section ordering and the aggregate aggregation.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.evaluation import EvaluationSummary, PipelineTrace
from src.infrastructure.reporting.table_formatter import TableFormatter
from src.infrastructure.reporting.trace_formatter import TraceFormatter


@dataclass(frozen=True)
class MarkdownDocumentBuilder:
    """Composes section blocks into a single Markdown report."""

    table_formatter: TableFormatter
    trace_formatter: TraceFormatter
    config_descriptions: tuple[tuple[str, str], ...] = ()
    llm_provider: str | None = None
    llm_model: str | None = None

    def build(
        self,
        summaries: list[EvaluationSummary],
        traces: list[PipelineTrace],
    ) -> str:
        descriptions = dict(self.config_descriptions)
        sections: list[str] = ["# Evaluation Report\n"]

        if self.llm_provider or self.llm_model:
            sections.append("## Generation Model\n")
            if self.llm_provider:
                sections.append(f"- **Provider**: {self.llm_provider}")
            if self.llm_model:
                sections.append(f"- **Model**: {self.llm_model}")
            sections.append("")

        labels_in_run = sorted({s.config_label for s in summaries})
        if labels_in_run and any(descriptions.get(lbl) for lbl in labels_in_run):
            sections.append("## Config Legend\n")
            for lbl in labels_in_run:
                desc = descriptions.get(lbl, "—")
                sections.append(f"- **{lbl}** — {desc}")
            sections.append("")

        sections.append("## Summary\n")
        sections.append(self.table_formatter.format_summary(summaries))
        sections.append("")

        config_labels = sorted({s.config_label for s in summaries})
        if config_labels:
            sections.append("## Aggregate by Config\n")
            for label in config_labels:
                rows = [s for s in summaries if s.config_label == label]
                avg_meter = sum(r.meter_accuracy for r in rows) / len(rows)
                avg_rhyme = sum(r.rhyme_accuracy for r in rows) / len(rows)
                avg_iters = sum(r.num_iterations for r in rows) / len(rows)
                errors = sum(1 for r in rows if r.error)
                sections.append(
                    f"- **Config {label}**: "
                    f"meter={avg_meter:.2%}  rhyme={avg_rhyme:.2%}  "
                    f"avg_iters={avg_iters:.1f}  errors={errors}/{len(rows)}",
                )
            sections.append("")

        if any(s.total_tokens or s.estimated_cost_usd for s in summaries):
            sections.append("## Tokens & Cost\n")
            sections.append(
                "| Config | Runs | Input tok | Output tok | Total tok "
                "| Cost, $ | Tok/run | $/run |",
            )
            sections.append(
                "|--------|------|-----------|------------|-----------"
                "|---------|---------|-------|",
            )
            for label in config_labels:
                rows = [s for s in summaries if s.config_label == label]
                in_tot = sum(r.input_tokens for r in rows)
                out_tot = sum(r.output_tokens for r in rows)
                tot = sum(r.total_tokens for r in rows)
                cost = sum(r.estimated_cost_usd for r in rows)
                n = len(rows) or 1
                sections.append(
                    f"| {label} | {len(rows)} | {in_tot:,} | {out_tot:,} "
                    f"| {tot:,} | ${cost:.4f} | {tot / n:.0f} | ${cost / n:.4f} |",
                )
            grand_in = sum(s.input_tokens for s in summaries)
            grand_out = sum(s.output_tokens for s in summaries)
            grand_tot = sum(s.total_tokens for s in summaries)
            grand_cost = sum(s.estimated_cost_usd for s in summaries)
            n_all = len(summaries) or 1
            sections.append(
                f"| **TOTAL** | **{len(summaries)}** | **{grand_in:,}** "
                f"| **{grand_out:,}** | **{grand_tot:,}** "
                f"| **${grand_cost:.4f}** | **{grand_tot / n_all:.0f}** "
                f"| **${grand_cost / n_all:.4f}** |",
            )
            sections.append("")

        if traces:
            sections.append("## Trace Details\n")
            for trace in traces:
                sections.append("<details>")
                sections.append(
                    f"<summary>Scenario {trace.scenario_id} / "
                    f"Config {trace.config_label}</summary>\n",
                )
                sections.append("```")
                sections.append(self.trace_formatter.format_trace(trace))
                sections.append("```")
                sections.append("</details>\n")

        return "\n".join(sections)
