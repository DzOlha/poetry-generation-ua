"""Markdown reporter — renders evaluation results as Markdown / plain text."""
from __future__ import annotations

from src.domain.evaluation import EvaluationSummary, PipelineTrace
from src.domain.models import Poem
from src.domain.ports import IReporter


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
    ) -> None:
        self._scenario_name_width = scenario_name_width
        self._error_width = error_width
        self._llm_provider = llm_provider
        self._llm_model = llm_model
        self._config_descriptions = dict(config_descriptions or {})

    # ------------------------------------------------------------------
    # IReporter
    # ------------------------------------------------------------------

    def format_summary_table(self, summaries: list[EvaluationSummary]) -> str:
        header = (
            "| Scenario | Meter | Config | Config Description | Meter% | Rhyme% "
            "| Iters | Lines | Time(s) | Error |"
        )
        sep = (
            "|----------|-------|--------|--------------------|--------|--------"
            "|-------|-------|---------|-------|"
        )
        rows = [header, sep]
        for s in summaries:
            err = (s.error or "—")[: self._error_width] if s.error else "—"
            meter_col = f"{s.meter} {s.foot_count}st {s.rhyme_scheme}"
            desc = self._config_descriptions.get(s.config_label, "—")
            rows.append(
                f"| {s.scenario_id} {s.scenario_name[: self._scenario_name_width]} "
                f"| {meter_col} | {s.config_label} | {desc} "
                f"| {s.meter_accuracy:.2%} | {s.rhyme_accuracy:.2%} "
                f"| {s.num_iterations} | {s.num_lines} | {s.duration_sec:.2f} | {err} |"
            )
        return "\n".join(rows)

    def format_trace_detail(self, trace: PipelineTrace) -> str:
        parts: list[str] = [
            f"═══ Trace: scenario={trace.scenario_id}  config={trace.config_label} ═══"
        ]
        for stage in trace.stages:
            parts += [
                f"  ── {stage.name} ──",
                f"     input:   {stage.input_summary}",
                f"     output:  {stage.output_summary}",
            ]
            if stage.metrics:
                parts.append(f"     metrics: {stage.metrics}")
            if stage.error:
                parts.append(f"     ERROR:   {stage.error}")
            parts.append(f"     time:    {stage.duration_sec:.4f}s")

        if trace.iterations:
            parts.append("  ── Iteration history ──")
            for it in trace.iterations:
                parts.append(
                    f"     [{it.iteration}] meter={it.meter_accuracy:.2%} "
                    f"rhyme={it.rhyme_accuracy:.2%}  violations={len(it.feedback)}"
                )
            parts.append("  ── Intermediate poems (per iteration) ──")
            for it in trace.iterations:
                it_poem = Poem.from_text(it.poem_text)
                parts.append(
                    f"     [iter {it.iteration}] ({it_poem.line_count} lines, "
                    f"meter={it.meter_accuracy:.2%}, rhyme={it.rhyme_accuracy:.2%})"
                )
                if it_poem.is_empty:
                    parts.append("       (empty / unparsable)")
                else:
                    parts.extend(f"       | {line}" for line in it_poem.lines)

        poem = Poem.from_text(trace.final_poem)
        parts += [
            f"  ── Final poem ({poem.line_count} lines) ──",
            *[f"     | {line}" for line in poem.lines],
            f"  ── Final metrics: {trace.final_metrics}",
            f"  ── Total time: {trace.total_duration_sec:.2f}s",
        ]
        if trace.error:
            parts.append(f"  !! ERROR: {trace.error}")
        return "\n".join(parts)

    def format_markdown_report(
        self,
        summaries: list[EvaluationSummary],
        traces: list[PipelineTrace],
    ) -> str:
        sections: list[str] = ["# Evaluation Report\n"]

        if self._llm_provider or self._llm_model:
            sections.append("## Generation Model\n")
            if self._llm_provider:
                sections.append(f"- **Provider**: {self._llm_provider}")
            if self._llm_model:
                sections.append(f"- **Model**: {self._llm_model}")
            sections.append("")

        labels_in_run = sorted({s.config_label for s in summaries})
        if labels_in_run and any(
            self._config_descriptions.get(lbl) for lbl in labels_in_run
        ):
            sections.append("## Config Legend\n")
            for lbl in labels_in_run:
                desc = self._config_descriptions.get(lbl, "—")
                sections.append(f"- **{lbl}** — {desc}")
            sections.append("")

        sections.append("## Summary\n")
        sections.append(self.format_summary_table(summaries))
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
                    f"avg_iters={avg_iters:.1f}  errors={errors}/{len(rows)}"
                )
            sections.append("")

        if traces:
            sections.append("## Trace Details\n")
            for trace in traces:
                sections.append("<details>")
                sections.append(
                    f"<summary>Scenario {trace.scenario_id} / Config {trace.config_label}</summary>\n"
                )
                sections.append("```")
                sections.append(self.format_trace_detail(trace))
                sections.append("```")
                sections.append("</details>\n")

        return "\n".join(sections)
