"""Per-trace text formatter — extracted from ``MarkdownReporter``.

Renders one ``PipelineTrace`` as a plain-text block (later wrapped in a
fenced ``<details>`` element by the document builder). The formatter
delegates per-iteration cost arithmetic to the injected ``CostCalculator``.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.evaluation import PipelineTrace
from src.domain.models import Poem
from src.infrastructure.reporting.cost_calculator import CostCalculator


@dataclass(frozen=True)
class TraceFormatter:
    """Renders one ``PipelineTrace`` as a plain-text block."""

    cost_calculator: CostCalculator

    def format_trace(self, trace: PipelineTrace) -> str:
        parts: list[str] = [
            f"═══ Trace: scenario={trace.scenario_id}  config={trace.config_label} ═══",
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
                tok_str = ""
                if it.input_tokens or it.output_tokens:
                    cost = self.cost_calculator.cost_for(it.input_tokens, it.output_tokens)
                    cost_part = f"  cost=${cost:.5f}" if cost > 0 else ""
                    tok_str = (
                        f"  tokens=in:{it.input_tokens:,}/out:{it.output_tokens:,}"
                        f"{cost_part}"
                    )
                parts.append(
                    f"     [{it.iteration}] meter={it.meter_accuracy:.2%} "
                    f"rhyme={it.rhyme_accuracy:.2%}  violations={len(it.feedback)}"
                    f"{tok_str}",
                )
            parts.append("  ── Intermediate poems (per iteration) ──")
            for it in trace.iterations:
                it_poem = Poem.from_text(it.poem_text)
                parts.append(
                    f"     [iter {it.iteration}] ({it_poem.line_count} lines, "
                    f"meter={it.meter_accuracy:.2%}, rhyme={it.rhyme_accuracy:.2%})",
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
        fm = trace.final_metrics
        in_tok = int(fm.get("input_tokens", 0))
        out_tok = int(fm.get("output_tokens", 0))
        tot_tok = int(fm.get("total_tokens", in_tok + out_tok))
        cost = float(fm.get("estimated_cost_usd", 0.0))
        if tot_tok or cost:
            parts.append(
                f"  ── Tokens & cost: in={in_tok:,}  out={out_tok:,}  "
                f"total={tot_tok:,}  estimated=${cost:.5f}",
            )
        if trace.error:
            parts.append(f"  !! ERROR: {trace.error}")
        return "\n".join(parts)
