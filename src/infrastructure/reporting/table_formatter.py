"""Markdown summary-table builder — extracted from ``MarkdownReporter``.

Holds the column layout and the per-row rendering rules. Kept small and
state-free so any reporter (Markdown, HTML, plain-text dashboard) can
reuse the same column truncation and formatting decisions.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.evaluation import EvaluationSummary


@dataclass(frozen=True)
class TableFormatter:
    """Renders a list of evaluation summaries as a Markdown table."""

    scenario_name_width: int = 20
    error_width: int = 30
    config_descriptions: tuple[tuple[str, str], ...] = ()

    def format_summary(self, summaries: list[EvaluationSummary]) -> str:
        descriptions = dict(self.config_descriptions)
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
            err = (s.error or "—")[: self.error_width] if s.error else "—"
            meter_col = f"{s.meter} {s.foot_count}st {s.rhyme_scheme}"
            desc = descriptions.get(s.config_label, "—")
            rows.append(
                f"| {s.scenario_id} {s.scenario_name[: self.scenario_name_width]} "
                f"| {meter_col} | {s.config_label} | {desc} "
                f"| {s.meter_accuracy:.2%} | {s.rhyme_accuracy:.2%} "
                f"| {s.num_iterations} | {s.num_lines} | {s.duration_sec:.2f} "
                f"| {err} |"
            )
        return "\n".join(rows)
