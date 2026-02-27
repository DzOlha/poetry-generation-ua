"""Evaluation runner — executes scenarios × ablation configs with full tracing.

Ablation configurations (from spec §9):
  A: Baseline (pure LLM)        — no retrieval, no validation, no feedback
  B: LLM + Validator             — no retrieval, validation on, no feedback
  C: LLM + Val + Feedback        — no retrieval, validation + feedback
  D: Full system                 — retrieval + validation + feedback
  E: No Retrieval                — validation + feedback, no retrieval

Each run produces a PipelineTrace with stage-by-stage records and metrics.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from src.evaluation.metrics import (
    bleu_score,
    meter_accuracy,
    rhyme_accuracy,
    rouge_l_score,
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
    use_validation: bool
    use_feedback: bool
    description: str = ""


ABLATION_CONFIGS: list[AblationConfig] = [
    AblationConfig("A", False, False, False, "Baseline (pure LLM)"),
    AblationConfig("B", False, True,  False, "LLM + Validator"),
    AblationConfig("C", False, True,  True,  "LLM + Val + Feedback"),
    AblationConfig("D", True,  True,  True,  "Full system"),
    AblationConfig("E", False, True,  True,  "No Retrieval (= C with explicit label)"),
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
            output_summary=f"retrieved {len(retrieved)} poems, top_sim={retrieved[0].similarity:.4f}" if retrieved else "no results",
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

    # ── Stage 2: Prompt construction ────────────────────────────────────
    with StageTimer() as t:
        prompt = build_rag_prompt(
            theme=scenario.theme,
            meter=scenario.meter,
            rhyme_scheme=scenario.rhyme_scheme,
            retrieved=retrieved,
            stanza_count=scenario.stanza_count,
            lines_per_stanza=scenario.lines_per_stanza,
        )
    trace.add_stage(StageRecord(
        name="prompt_construction",
        input_summary=f"theme={scenario.theme!r}, meter={scenario.meter}, scheme={scenario.rhyme_scheme}, structure={scenario.stanza_count}×{scenario.lines_per_stanza}",
        input_data={
            "theme": scenario.theme,
            "meter": scenario.meter,
            "rhyme_scheme": scenario.rhyme_scheme,
            "foot_count": scenario.foot_count,
            "stanza_count": scenario.stanza_count,
            "lines_per_stanza": scenario.lines_per_stanza,
            "total_lines": scenario.total_lines,
            "num_retrieved": len(retrieved),
        },
        output_summary=f"prompt length={len(prompt)} chars",
        output_data=prompt,
        metrics={"prompt_length": len(prompt)},
        duration_sec=t.elapsed,
    ))

    # ── Stage 3: Initial generation ─────────────────────────────────────
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

    # ── Stage 4: Validation (meter + rhyme) ─────────────────────────────
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
            m_results = check_meter_poem(poem, meter=scenario.meter, foot_count=scenario.foot_count, stress_dict=stress_dict)
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

    # ── Stage 5: Feedback loop ──────────────────────────────────────────
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
                m_results = check_meter_poem(poem, meter=scenario.meter, foot_count=scenario.foot_count, stress_dict=stress_dict)
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
        input_data={"max_iterations": max_iterations, "initial_poem": trace.iterations[0].poem_text if trace.iterations else ""},
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

    if scenario.reference_poem:
        metrics["bleu"] = bleu_score(poem, scenario.reference_poem)
        metrics["rouge_l"] = rouge_l_score(poem, scenario.reference_poem)
    else:
        metrics["bleu"] = None
        metrics["rouge_l"] = None

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
    meter_accuracy: float
    rhyme_accuracy: float
    bleu: float | None
    rouge_l: float | None
    num_iterations: int
    num_lines: int
    duration_sec: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "config": self.config_label,
            "meter_accuracy": round(self.meter_accuracy, 4),
            "rhyme_accuracy": round(self.rhyme_accuracy, 4),
            "bleu": round(self.bleu, 4) if self.bleu is not None else None,
            "rouge_l": round(self.rouge_l, 4) if self.rouge_l is not None else None,
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
        meter_accuracy=fm.get("meter_accuracy", 0.0),
        rhyme_accuracy=fm.get("rhyme_accuracy", 0.0),
        bleu=fm.get("bleu"),
        rouge_l=fm.get("rouge_l"),
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
            )
            traces.append(trace)
            summaries.append(_summary_from_trace(trace, scenario))

    return traces, summaries


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def format_summary_table(summaries: list[EvaluationSummary]) -> str:
    """Format summaries as a Markdown table."""
    header = "| Scenario | Config | Meter% | Rhyme% | BLEU | ROUGE-L | Iters | Lines | Time(s) | Error |"
    sep =    "|----------|--------|--------|--------|------|---------|-------|-------|---------|-------|"
    rows = [header, sep]
    for s in summaries:
        bleu = f"{s.bleu:.4f}" if s.bleu is not None else "—"
        rouge = f"{s.rouge_l:.4f}" if s.rouge_l is not None else "—"
        err = s.error[:30] if s.error else "—"
        rows.append(
            f"| {s.scenario_id} {s.scenario_name[:20]} | {s.config_label} "
            f"| {s.meter_accuracy:.2%} | {s.rhyme_accuracy:.2%} "
            f"| {bleu} | {rouge} | {s.num_iterations} | {s.num_lines} "
            f"| {s.duration_sec:.2f} | {err} |"
        )
    return "\n".join(rows)


def format_trace_detail(trace: PipelineTrace) -> str:
    """Format a single trace as readable text with full data."""
    parts: list[str] = [
        f"═══ Trace: scenario={trace.scenario_id}  config={trace.config_label} ═══",
    ]
    for stage in trace.stages:
        parts.append(f"  ── {stage.name} ──")
        parts.append(f"     input:   {stage.input_summary}")
        if stage.input_data is not None:
            parts.append(f"     ┌─ INPUT DATA ─")
            _append_data(parts, stage.input_data)
        parts.append(f"     output:  {stage.output_summary}")
        if stage.output_data is not None:
            parts.append(f"     ┌─ OUTPUT DATA ─")
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
            parts.append(f"       poem:")
            for line in split_nonempty_lines(it.poem_text):
                parts.append(f"         | {line}")
            if it.feedback:
                parts.append(f"       feedback:")
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
