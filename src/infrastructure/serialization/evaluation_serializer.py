"""Serialization functions for evaluation domain objects.

Extracted from domain `to_dict()` methods so the domain layer stays free
of serialization concerns (JSON field names, rounding, conditional inclusion).
"""
from __future__ import annotations

from typing import Any

from src.domain.evaluation import (
    EvaluationSummary,
    IterationRecord,
    PipelineTrace,
    StageRecord,
)


def evaluation_summary_to_dict(s: EvaluationSummary) -> dict[str, Any]:
    """Serialize an EvaluationSummary to a JSON-friendly dict."""
    return {
        "scenario_id": s.scenario_id,
        "scenario_name": s.scenario_name,
        "config": s.config_label,
        "meter": s.meter,
        "foot_count": s.foot_count,
        "rhyme_scheme": s.rhyme_scheme,
        "meter_accuracy": round(s.meter_accuracy, 4),
        "rhyme_accuracy": round(s.rhyme_accuracy, 4),
        "iterations": s.num_iterations,
        "lines": s.num_lines,
        "duration_sec": round(s.duration_sec, 4),
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens,
        "total_tokens": s.total_tokens,
        "estimated_cost_usd": round(s.estimated_cost_usd, 6),
        "error": s.error,
    }


def stage_record_to_dict(rec: StageRecord) -> dict[str, Any]:
    """Serialize a StageRecord to a JSON-friendly dict."""
    d: dict[str, Any] = {
        "stage": rec.name,
        "input": rec.input_summary,
        "output": rec.output_summary,
        "metrics": rec.metrics,
        "duration_sec": round(rec.duration_sec, 4),
    }
    if rec.input_data is not None:
        d["input_data"] = rec.input_data
    if rec.output_data is not None:
        d["output_data"] = rec.output_data
    if rec.error:
        d["error"] = rec.error
    return d


def iteration_record_to_dict(rec: IterationRecord) -> dict[str, Any]:
    """Serialize an IterationRecord to a JSON-friendly dict."""
    return {
        "iteration": rec.iteration,
        "poem_text": rec.poem_text,
        "meter_accuracy": round(rec.meter_accuracy, 4),
        "rhyme_accuracy": round(rec.rhyme_accuracy, 4),
        "feedback": rec.feedback,
        "duration_sec": round(rec.duration_sec, 4),
        "raw_llm_response": rec.raw_llm_response,
        "sanitized_llm_response": rec.sanitized_llm_response,
        "input_tokens": rec.input_tokens,
        "output_tokens": rec.output_tokens,
    }


def pipeline_trace_to_dict(t: PipelineTrace) -> dict[str, Any]:
    """Serialize a PipelineTrace to a JSON-friendly dict."""
    d: dict[str, Any] = {
        "scenario_id": t.scenario_id,
        "config": t.config_label,
        "stages": [stage_record_to_dict(s) for s in t.stages],
        "iterations": [iteration_record_to_dict(it) for it in t.iterations],
        "final_poem": t.final_poem,
        "final_metrics": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in t.final_metrics.items()
        },
        "total_duration_sec": round(t.total_duration_sec, 4),
    }
    if t.error:
        d["error"] = t.error
    return d
