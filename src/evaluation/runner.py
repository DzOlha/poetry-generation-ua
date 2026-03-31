"""Evaluation runner — executes scenarios × ablation configs with full tracing.

Ablation configurations:
  A: Baseline (LLM + Validator)    — no retrieval, no feedback; measures native LLM quality
  B: LLM + Val + Feedback          — no retrieval, feedback loop on
  C: Semantic RAG + Val + Feedback — semantic retrieval only, no metric examples
  D: Metric Examples + Val + Feedback — metric examples only, no semantic retrieval
  E: Full system                   — semantic retrieval + metric examples + validation + feedback

Comparing configs isolates each component's contribution:
  A→B: impact of feedback loop
  B→C: impact of semantic retrieval (thematic RAG)
  B→D: impact of metric examples retrieval (rhythm/rhyme RAG)
  C→E or D→E: impact of combining both retrieval types

Each run produces a PipelineTrace with stage-by-stage records and metrics.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from src.evaluation.metrics import (
    meter_accuracy,
    rhyme_accuracy,
)
from src.evaluation.scenarios import ALL_SCENARIOS, EvaluationScenario
from src.evaluation.trace import (
    IterationRecord,
    PipelineTrace,
    StageRecord,
    StageTimer,
)
from src.generation.llm import LLMClient, MockLLMClient, merge_regenerated_poem
from src.meter.stress import StressDict
from src.meter.validator import check_meter_poem, meter_feedback
from src.retrieval.corpus import CorpusPoem, corpus_from_env
from src.retrieval.metric_examples import find_metric_examples
from src.retrieval.retriever import SemanticRetriever, build_rag_prompt
from src.rhyme.validator import check_rhyme, rhyme_feedback
from src.utils.text import split_nonempty_lines

# ---------------------------------------------------------------------------
# Ablation config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AblationConfig:
    label: str
    use_retrieval: bool
    use_metric_examples: bool
    use_validation: bool
    use_feedback: bool
    description: str = ""


ABLATION_CONFIGS: list[AblationConfig] = [
    AblationConfig("A", False, False, True,  False, "Baseline (LLM + validator, no RAG, no feedback)"),
    AblationConfig("B", False, False, True,  True,  "LLM + Val + Feedback (no RAG)"),
    AblationConfig("C", True,  False, True,  True,  "Semantic RAG + Val + Feedback"),
    AblationConfig("D", False, True,  True,  True,  "Metric Examples + Val + Feedback"),
    AblationConfig("E", True,  True,  True,  True,  "Full system (semantic + metric examples + val + feedback)"),
]


# ---------------------------------------------------------------------------
# Traced pipeline run
# ---------------------------------------------------------------------------

def run_traced_pipeline(
    scenario: EvaluationScenario,
    config: AblationConfig,
    *,
    llm: LLMClient | None = None,
    stress_dict: StressDict | None = None,
    retriever: SemanticRetriever | None = None,
    corpus: list[CorpusPoem] | None = None,
    max_iterations: int = 1,
    top_k: int = 5,
    metric_examples_path: str = "corpus/ukrainian_poetry_dataset.json",
    metric_examples_top_k: int = 2,
) -> PipelineTrace:
    """Run a single scenario under one ablation config, returning a full trace."""

    trace = PipelineTrace(scenario_id=scenario.id, config_label=config.label)
    t_global = time.perf_counter()

    llm = llm or MockLLMClient()
    stress_dict = stress_dict or StressDict(on_ambiguity="first")
    retriever = retriever or SemanticRetriever()
    corpus = corpus if corpus is not None else corpus_from_env()

    # ── Stage 1: Retrieval ──────────────────────────────────────────────
    retrieved = []
    if config.use_retrieval and corpus:
        with StageTimer() as t:
            try:
                retrieved = retriever.retrieve(scenario.theme, corpus, top_k=top_k)
            except Exception as exc:
                trace.add_stage(StageRecord(
                    name="retrieval",
                    input_summary=f"theme={scenario.theme!r}, corpus_size={len(corpus)}",
                    input_data={"theme": scenario.theme, "corpus_size": len(corpus)},
                    error=str(exc),
                ))
        retrieved_data = [
            {"poem_id": r.poem_id, "similarity": round(r.similarity, 4), "text": r.text}
            for r in retrieved
        ]
        trace.add_stage(StageRecord(
            name="retrieval",
            input_summary=f"theme={scenario.theme!r}, corpus_size={len(corpus)}",
            input_data={"theme": scenario.theme, "corpus_size": len(corpus)},
            output_summary=(
                f"retrieved {len(retrieved)} poems, top_sim={retrieved[0].similarity:.4f}"
                if retrieved else "no results"
            ),
            output_data=retrieved_data,
            metrics={"num_retrieved": len(retrieved), "top_similarity": retrieved[0].similarity if retrieved else 0.0},
            duration_sec=t.elapsed,
        ))
    else:
        trace.add_stage(StageRecord(
            name="retrieval",
            input_summary="SKIPPED (config.use_retrieval=False or empty corpus)",
            output_summary="—",
            metrics={"num_retrieved": 0},
        ))

    # ── Stage 2: Metric examples retrieval ──────────────────────────────
    metric_examples = []
    if config.use_metric_examples:
        with StageTimer() as t:
            try:
                metric_examples = find_metric_examples(
                    meter=scenario.meter,
                    feet=scenario.foot_count,
                    scheme=scenario.rhyme_scheme,
                    dataset_path=metric_examples_path,
                    top_k=metric_examples_top_k,
                )
            except Exception as exc:
                trace.add_stage(StageRecord(
                    name="metric_examples",
                    input_summary=f"meter={scenario.meter}, feet={scenario.foot_count}, scheme={scenario.rhyme_scheme}",
                    error=str(exc),
                ))
                metric_examples = []
        if not trace.stages or trace.stages[-1].name != "metric_examples":
            trace.add_stage(StageRecord(
                name="metric_examples",
                input_summary=f"meter={scenario.meter}, feet={scenario.foot_count}, scheme={scenario.rhyme_scheme}",
                output_summary=f"found {len(metric_examples)} metric examples",
                output_data=[
                    {
                        "id": e.id,
                        "meter": e.meter,
                        "feet": e.feet,
                        "scheme": e.scheme,
                        "verified": e.verified,
                        "author": e.author,
                        "text": e.text,
                    }
                    for e in metric_examples
                ],
                metrics={"num_examples": len(metric_examples)},
                duration_sec=t.elapsed,
            ))
    else:
        trace.add_stage(StageRecord(
            name="metric_examples",
            input_summary="SKIPPED (config.use_metric_examples=False)",
            output_summary="—",
            metrics={"num_examples": 0},
        ))

    # ── Stage 3: Prompt construction ────────────────────────────────────
    with StageTimer() as t:
        prompt = build_rag_prompt(
            theme=scenario.theme,
            meter=scenario.meter,
            rhyme_scheme=scenario.rhyme_scheme,
            retrieved=retrieved,
            stanza_count=scenario.stanza_count,
            lines_per_stanza=scenario.lines_per_stanza,
            metric_examples=metric_examples if metric_examples else None,
        )
    trace.add_stage(StageRecord(
        name="prompt_construction",
        input_summary=(
            f"theme={scenario.theme!r}, meter={scenario.meter}, scheme={scenario.rhyme_scheme}, "
            f"structure={scenario.stanza_count}×{scenario.lines_per_stanza}"
        ),
        input_data={
            "theme": scenario.theme,
            "meter": scenario.meter,
            "rhyme_scheme": scenario.rhyme_scheme,
            "foot_count": scenario.foot_count,
            "stanza_count": scenario.stanza_count,
            "lines_per_stanza": scenario.lines_per_stanza,
            "total_lines": scenario.total_lines,
            "num_retrieved": len(retrieved),
            "num_metric_examples": len(metric_examples),
        },
        output_summary=f"prompt length={len(prompt)} chars",
        output_data=prompt,
        metrics={"prompt_length": len(prompt), "num_metric_examples": len(metric_examples)},
        duration_sec=t.elapsed,
    ))

    # ── Stage 4: Initial generation ─────────────────────────────────────
    with StageTimer() as t:
        try:
            poem = llm.generate(prompt).text
        except Exception as exc:
            trace.error = f"generation failed: {exc}"
            trace.total_duration_sec = time.perf_counter() - t_global
            return trace
    lines = split_nonempty_lines(poem)
    trace.add_stage(StageRecord(
        name="initial_generation",
        input_summary=f"prompt ({len(prompt)} chars)",
        input_data=prompt,
        output_summary=f"{len(lines)} lines generated",
        output_data=poem,
        metrics={"num_lines": len(lines)},
        duration_sec=t.elapsed,
    ))

    # ── Stage 5: Validation (meter + rhyme) ─────────────────────────────
    if not config.use_validation:
        trace.add_stage(StageRecord(
            name="validation",
            input_summary="SKIPPED (config.use_validation=False)",
            input_data=poem,
            output_summary="—",
        ))
        trace.final_poem = poem
        _compute_final_metrics(trace, scenario, poem, stress_dict)
        trace.total_duration_sec = time.perf_counter() - t_global
        return trace

    with StageTimer() as t:
        try:
            m_results = check_meter_poem(
                poem, meter=scenario.meter, foot_count=scenario.foot_count, stress_dict=stress_dict
            )
            r_result = check_rhyme(poem, scheme=scenario.rhyme_scheme, stress_dict=stress_dict)
        except Exception as exc:
            trace.add_stage(StageRecord(name="validation", input_data=poem, error=str(exc)))
            trace.final_poem = poem
            _compute_final_metrics(trace, scenario, poem, stress_dict)
            trace.total_duration_sec = time.perf_counter() - t_global
            return trace

    m_acc = (sum(1 for r in m_results if r.ok) / len(m_results)) if m_results else 1.0
    r_acc = (sum(1 for p in r_result.pairs if p.rhyme_ok) / len(r_result.pairs)) if r_result.pairs else 1.0
    fb: list[str] = []
    for i, res in enumerate(m_results):
        if not res.ok:
            fb.append(meter_feedback(i, scenario.meter, res))
    for pair in r_result.pairs:
        if not pair.rhyme_ok:
            fb.append(rhyme_feedback(pair, scenario.rhyme_scheme))

    meter_details = [
        {
            "line": i + 1,
            "ok": r.ok,
            "expected_stress": r.expected_stress_syllables_1based,
            "actual_stress": r.actual_stress_syllables_1based,
            "error_positions": r.errors_positions_1based,
            "total_syllables": r.total_syllables,
        }
        for i, r in enumerate(m_results)
    ]
    rhyme_details = [
        {
            "line_1": p.line_1,
            "line_2": p.line_2,
            "word_1": p.word_1,
            "word_2": p.word_2,
            "rhyme_part_1": p.rhyme_part_1,
            "rhyme_part_2": p.rhyme_part_2,
            "score": round(p.score, 4),
            "rhyme_ok": p.rhyme_ok,
        }
        for p in r_result.pairs
    ]
    trace.add_stage(StageRecord(
        name="validation",
        input_summary=f"poem ({len(lines)} lines)",
        input_data=poem,
        output_summary=f"meter_acc={m_acc:.2%}, rhyme_acc={r_acc:.2%}, violations={len(fb)}",
        output_data={
            "meter_results": meter_details,
            "rhyme_results": rhyme_details,
            "feedback": fb,
        },
        metrics={"meter_accuracy": m_acc, "rhyme_accuracy": r_acc, "violation_count": len(fb)},
        duration_sec=t.elapsed,
    ))

    trace.add_iteration(IterationRecord(
        iteration=0,
        poem_text=poem,
        meter_accuracy=m_acc,
        rhyme_accuracy=r_acc,
        feedback=fb,
        duration_sec=t.elapsed,
    ))

    # ── Stage 6: Feedback loop ──────────────────────────────────────────
    if not config.use_feedback:
        trace.add_stage(StageRecord(
            name="feedback_loop",
            input_summary="SKIPPED (config.use_feedback=False)",
            output_summary="—",
        ))
        trace.final_poem = poem
        _compute_final_metrics(trace, scenario, poem, stress_dict)
        trace.total_duration_sec = time.perf_counter() - t_global
        return trace

    meter_ok = all(r.ok for r in m_results) if m_results else True
    rhyme_ok = r_result.is_valid

    for it in range(1, max_iterations + 1):
        if meter_ok and rhyme_ok:
            break
        with StageTimer() as t_iter:
            try:
                prev_poem = poem
                poem = llm.regenerate_lines(poem, fb).text
                poem = merge_regenerated_poem(prev_poem, poem, fb)
                m_results = check_meter_poem(
                poem, meter=scenario.meter, foot_count=scenario.foot_count, stress_dict=stress_dict
            )
                r_result = check_rhyme(poem, scheme=scenario.rhyme_scheme, stress_dict=stress_dict)
            except Exception as exc:
                trace.add_stage(StageRecord(name=f"feedback_iter_{it}", error=str(exc)))
                break

        m_acc = (sum(1 for r in m_results if r.ok) / len(m_results)) if m_results else 1.0
        r_acc = (sum(1 for p in r_result.pairs if p.rhyme_ok) / len(r_result.pairs)) if r_result.pairs else 1.0
        fb = []
        for i, res in enumerate(m_results):
            if not res.ok:
                fb.append(meter_feedback(i, scenario.meter, res))
        for pair in r_result.pairs:
            if not pair.rhyme_ok:
                fb.append(rhyme_feedback(pair, scenario.rhyme_scheme))

        meter_ok = all(r.ok for r in m_results) if m_results else True
        rhyme_ok = r_result.is_valid

        trace.add_iteration(IterationRecord(
            iteration=it,
            poem_text=poem,
            meter_accuracy=m_acc,
            rhyme_accuracy=r_acc,
            feedback=fb,
            duration_sec=t_iter.elapsed,
        ))

    trace.add_stage(StageRecord(
        name="feedback_loop",
        input_summary=f"max_iterations={max_iterations}",
        input_data={
            "max_iterations": max_iterations,
            "initial_poem": trace.iterations[0].poem_text if trace.iterations else "",
        },
        output_summary=f"{len(trace.iterations)} iterations total, final meter={m_acc:.2%} rhyme={r_acc:.2%}",
        output_data={
            "final_poem": poem,
            "final_feedback": fb,
        },
        metrics={
            "total_iterations": len(trace.iterations),
            "final_meter_accuracy": m_acc,
            "final_rhyme_accuracy": r_acc,
            "final_violations": len(fb),
        },
    ))

    trace.final_poem = poem
    _compute_final_metrics(trace, scenario, poem, stress_dict)
    trace.total_duration_sec = time.perf_counter() - t_global
    return trace


# ---------------------------------------------------------------------------
# Final metrics helper
# ---------------------------------------------------------------------------

def _compute_final_metrics(
    trace: PipelineTrace,
    scenario: EvaluationScenario,
    poem: str,
    stress_dict: StressDict,
) -> None:
    try:
        m_acc = meter_accuracy(poem, meter=scenario.meter, foot_count=scenario.foot_count, stress_dict=stress_dict)
    except Exception:
        m_acc = 0.0
    try:
        r_acc = rhyme_accuracy(poem, scheme=scenario.rhyme_scheme, stress_dict=stress_dict)
    except Exception:
        r_acc = 0.0

    metrics: dict[str, Any] = {
        "meter_accuracy": m_acc,
        "rhyme_accuracy": r_acc,
    }

    num_lines = len(split_nonempty_lines(poem))
    metrics["num_lines"] = num_lines

    if trace.iterations:
        init_m = trace.iterations[0].meter_accuracy
        init_r = trace.iterations[0].rhyme_accuracy
        final_m = trace.iterations[-1].meter_accuracy
        final_r = trace.iterations[-1].rhyme_accuracy
        metrics["meter_improvement"] = final_m - init_m
        metrics["rhyme_improvement"] = final_r - init_r
        metrics["feedback_iterations"] = len(trace.iterations) - 1

    trace.final_metrics = metrics


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

@dataclass
class EvaluationSummary:
    """Summary row for one (scenario, config) pair."""

    scenario_id: str
    scenario_name: str
    config_label: str
    meter: str
    foot_count: int
    rhyme_scheme: str
    meter_accuracy: float
    rhyme_accuracy: float
    num_iterations: int
    num_lines: int
    duration_sec: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "config": self.config_label,
            "meter": self.meter,
            "foot_count": self.foot_count,
            "rhyme_scheme": self.rhyme_scheme,
            "meter_accuracy": round(self.meter_accuracy, 4),
            "rhyme_accuracy": round(self.rhyme_accuracy, 4),
            "iterations": self.num_iterations,
            "lines": self.num_lines,
            "duration_sec": round(self.duration_sec, 4),
            "error": self.error,
        }


def _summary_from_trace(trace: PipelineTrace, scenario: EvaluationScenario) -> EvaluationSummary:
    fm = trace.final_metrics
    return EvaluationSummary(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        config_label=trace.config_label,
        meter=scenario.meter,
        foot_count=scenario.foot_count,
        rhyme_scheme=scenario.rhyme_scheme,
        meter_accuracy=fm.get("meter_accuracy", 0.0),
        rhyme_accuracy=fm.get("rhyme_accuracy", 0.0),
        num_iterations=fm.get("feedback_iterations", 0),
        num_lines=fm.get("num_lines", 0),
        duration_sec=trace.total_duration_sec,
        error=trace.error,
    )


def run_evaluation_matrix(
    scenarios: list[EvaluationScenario] | None = None,
    configs: list[AblationConfig] | None = None,
    *,
    llm: LLMClient | None = None,
    stress_dict: StressDict | None = None,
    retriever: SemanticRetriever | None = None,
    corpus: list[CorpusPoem] | None = None,
    max_iterations: int = 1,
    metric_examples_path: str = "corpus/ukrainian_poetry_dataset.json",
    metric_examples_top_k: int = 2,
) -> tuple[list[PipelineTrace], list[EvaluationSummary]]:
    """Run every scenario × config combination. Returns all traces and a summary table."""

    scenarios = scenarios or ALL_SCENARIOS
    configs = configs or ABLATION_CONFIGS

    traces: list[PipelineTrace] = []
    summaries: list[EvaluationSummary] = []

    for scenario in scenarios:
        for config in configs:
            trace = run_traced_pipeline(
                scenario,
                config,
                llm=llm,
                stress_dict=stress_dict,
                retriever=retriever,
                corpus=corpus,
                max_iterations=max_iterations,
                metric_examples_path=metric_examples_path,
                metric_examples_top_k=metric_examples_top_k,
            )
            traces.append(trace)
            summaries.append(_summary_from_trace(trace, scenario))

    return traces, summaries


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def format_summary_table(summaries: list[EvaluationSummary]) -> str:
    """Format summaries as a Markdown table."""
    header = "| Scenario | Meter | Config | Meter% | Rhyme% | Iters | Lines | Time(s) | Error |"
    sep =    "|----------|-------|--------|--------|--------|-------|-------|---------|-------|"
    rows = [header, sep]
    for s in summaries:
        err = s.error[:30] if s.error else "—"
        meter_col = f"{s.meter} {s.foot_count}st {s.rhyme_scheme}"
        rows.append(
            f"| {s.scenario_id} {s.scenario_name[:20]} | {meter_col} | {s.config_label} "
            f"| {s.meter_accuracy:.2%} | {s.rhyme_accuracy:.2%} "
            f"| {s.num_iterations} | {s.num_lines} "
            f"| {s.duration_sec:.2f} | {err} |"
        )
    return "\n".join(rows)


def format_markdown_report(
    summaries: list[EvaluationSummary],
    traces: list[PipelineTrace],
) -> str:
    """Format a human-readable Markdown report: summary table + final poem per config."""
    # Group by scenario so each scenario gets its own section
    scenario_ids: list[str] = list(dict.fromkeys(s.scenario_id for s in summaries))
    trace_index: dict[tuple[str, str], PipelineTrace] = {
        (t.scenario_id, t.config_label): t for t in traces
    }

    parts: list[str] = ["# Ablation Study Results", ""]

    for sid in scenario_ids:
        rows = [s for s in summaries if s.scenario_id == sid]
        name = rows[0].scenario_name if rows else sid
        first = rows[0] if rows else None
        meter_info = (
            f"{first.meter} {first.foot_count}-стопний, {first.rhyme_scheme}" if first else ""
        )
        parts += [f"## Scenario {sid} — {name}", f"*{meter_info}*", ""]

        # ── Summary table ──────────────────────────────────────────────
        parts.append("| Config | Description | Meter% | Rhyme% | Iters | Time(s) | Error |")
        parts.append("|--------|-------------|--------|--------|-------|---------|-------|")
        for s in rows:
            cfg_desc = next(
                (c.description for c in ABLATION_CONFIGS if c.label == s.config_label), ""
            )
            err = s.error[:40] if s.error else "—"
            parts.append(
                f"| **{s.config_label}** | {cfg_desc} "
                f"| {s.meter_accuracy:.1%} | {s.rhyme_accuracy:.1%} "
                f"| {s.num_iterations} | {s.duration_sec:.1f} | {err} |"
            )
        parts.append("")

        # ── Final poems ────────────────────────────────────────────────
        parts.append("### Final poems")
        parts.append("")
        for s in rows:
            trace = trace_index.get((sid, s.config_label))
            poem = trace.final_poem.strip() if trace else ""
            cfg_desc = next(
                (c.description for c in ABLATION_CONFIGS if c.label == s.config_label), ""
            )
            status = f"meter={s.meter_accuracy:.1%} rhyme={s.rhyme_accuracy:.1%}"
            if s.error:
                status += f" ERROR: {s.error[:60]}"
            parts.append(f"**Config {s.config_label}** ({cfg_desc}) — {status}")
            parts.append("")
            parts.append("```")
            parts.append(poem if poem else "(no poem generated)")
            parts.append("```")
            parts.append("")

    return "\n".join(parts)


def format_trace_detail(trace: PipelineTrace) -> str:
    """Format a single trace as readable text with full data."""
    parts: list[str] = [
        f"═══ Trace: scenario={trace.scenario_id}  config={trace.config_label} ═══",
    ]
    for stage in trace.stages:
        parts.append(f"  ── {stage.name} ──")
        parts.append(f"     input:   {stage.input_summary}")
        if stage.input_data is not None:
            parts.append("     ┌─ INPUT DATA ─")
            _append_data(parts, stage.input_data)
        parts.append(f"     output:  {stage.output_summary}")
        if stage.output_data is not None:
            parts.append("     ┌─ OUTPUT DATA ─")
            _append_data(parts, stage.output_data)
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
            parts.append("       poem:")
            for line in split_nonempty_lines(it.poem_text):
                parts.append(f"         | {line}")
            if it.feedback:
                parts.append("       feedback:")
                for fb_line in it.feedback:
                    parts.append(f"         • {fb_line}")
    parts.append(f"  ── Final poem ({len(split_nonempty_lines(trace.final_poem))} lines) ──")
    for line in split_nonempty_lines(trace.final_poem):
        parts.append(f"     | {line}")
    parts.append(f"  ── Final metrics: {trace.final_metrics}")
    parts.append(f"  ── Total time: {trace.total_duration_sec:.2f}s")
    if trace.error:
        parts.append(f"  !! ERROR: {trace.error}")
    parts.append("")
    return "\n".join(parts)


def _append_data(parts: list[str], data: Any) -> None:
    """Helper to format input/output data for verbose trace output."""
    if isinstance(data, str):
        for line in data.splitlines():
            parts.append(f"     │ {line}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                parts.append(f"     │ [{i}] {item}")
            else:
                parts.append(f"     │ [{i}] {item}")
    elif isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str) and "\n" in val:
                parts.append(f"     │ {key}:")
                for line in val.splitlines():
                    parts.append(f"     │   {line}")
            elif isinstance(val, list):
                parts.append(f"     │ {key}: ({len(val)} items)")
                for item in val:
                    parts.append(f"     │   {item}")
            else:
                parts.append(f"     │ {key}: {val}")
    else:
        parts.append(f"     │ {data}")
