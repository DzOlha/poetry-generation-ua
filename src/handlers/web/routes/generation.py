"""Web UI — poem generation and validation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.errors import DomainError
from src.domain.evaluation import IterationRecord
from src.domain.models import (
    GenerationRequest,
    LineMeterResult,
    MeterSpec,
    PoemStructure,
    RhymeScheme,
    ValidationRequest,
)
from src.domain.ports import (
    EvaluationContext,
    IFeedbackFormatter,
    IMetricCalculatorRegistry,
    format_all_feedback,
)
from src.handlers.api.dependencies import (
    get_feedback_formatter,
    get_metric_registry,
    get_poetry_service,
)
from src.handlers.web.routes._shared import templates
from src.services.poetry_service import PoetryService
from src.shared.text_utils_ua import VOWELS_UA

router = APIRouter()


def _line_segments(
    text: str,
    expected: set[int],
    actual: set[int],
) -> list[dict[str, object]]:
    """Split a line into char-level segments, tagging the k-th vowel with its stress role."""
    segments: list[dict[str, object]] = []
    vowel_idx = 0
    for ch in text:
        if ch.lower() in VOWELS_UA:
            vowel_idx += 1
            exp = vowel_idx in expected
            act = vowel_idx in actual
            if exp and act:
                tag = "both"
            elif exp:
                tag = "exp"
            elif act:
                tag = "act"
            else:
                tag = ""
            segments.append({"ch": ch, "tag": tag})
        else:
            segments.append({"ch": ch, "tag": ""})
    return segments


def _line_displays(
    poem_text: str,
    line_results: tuple[LineMeterResult, ...],
) -> list[dict[str, object]]:
    """Pair raw poem lines with their per-line meter results for UI rendering."""
    results = iter(line_results)
    displays: list[dict[str, object]] = []
    for raw in poem_text.splitlines():
        text = raw.strip()
        if not text:
            displays.append({"blank": True})
            continue
        result = next(results, None)
        if result is None:
            displays.append({"blank": False, "text": text, "segments": None})
            continue
        expected_set = set(result.expected_stresses)
        actual_set = set(result.actual_stresses)
        expected_len = max(result.total_syllables, max(expected_set, default=0))
        actual_len = result.total_syllables
        diff = actual_len - expected_len
        if diff > 0:
            length_note = f"на {diff} склад(и/ів) довше очікуваного ({expected_len})"
        elif diff < 0:
            length_note = f"на {-diff} склад(и/ів) коротше очікуваного ({expected_len})"
        else:
            length_note = ""
        displays.append({
            "blank": False,
            "text": text,
            "ok": result.ok,
            "segments": _line_segments(text, expected_set, actual_set),
            "annotation": result.annotation,
            "length_note": length_note,
        })
    return displays


@router.post("/generate", response_class=HTMLResponse)
def generate_web(
    request: Request,
    theme: str = Form(..., min_length=1),
    meter: str = Form("ямб"),
    feet: int = Form(4, ge=1, le=8),
    scheme: str = Form("ABAB"),
    stanzas: int = Form(4, ge=1, le=10),
    iterations: int = Form(3, ge=0, le=3),
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
    metric_registry: IMetricCalculatorRegistry = Depends(get_metric_registry),
) -> HTMLResponse:
    try:
        gen_request = GenerationRequest(
            theme=theme,
            meter=MeterSpec(name=meter, foot_count=feet),
            rhyme=RhymeScheme(pattern=scheme),
            structure=PoemStructure(stanza_count=stanzas, lines_per_stanza=4),
            max_iterations=iterations,
        )
        result = service.generate(gen_request)
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": str(exc)},
        )
    iter_records = [
        IterationRecord(
            iteration=s.iteration,
            poem_text=s.poem,
            meter_accuracy=s.meter_accuracy,
            rhyme_accuracy=s.rhyme_accuracy,
            feedback=tuple(s.feedback),
            duration_sec=s.duration_sec,
        )
        for s in result.iteration_history
    ]
    ctx = EvaluationContext(
        poem_text=result.poem,
        meter=gen_request.meter,
        rhyme=gen_request.rhyme,
        iterations=iter_records,
        theme=theme,
    )
    extra_metrics = {c.name: c.calculate(ctx) for c in metric_registry.all()}

    iteration_displays: list[list[dict[str, object]]] = []
    for snap in result.iteration_history:
        try:
            snap_val = service.validate(ValidationRequest(
                poem_text=snap.poem,
                meter=gen_request.meter,
                rhyme=gen_request.rhyme,
            ))
            iteration_displays.append(
                _line_displays(snap.poem, snap_val.meter.line_results),
            )
        except DomainError:
            iteration_displays.append([])

    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "poem": result.poem,
            "line_displays": _line_displays(result.poem, result.validation.meter.line_results),
            "theme": theme,
            "meter": meter,
            "feet": feet,
            "scheme": scheme,
            "is_valid": result.validation.is_valid,
            "meter_ok": result.validation.meter.ok,
            "rhyme_ok": result.validation.rhyme.ok,
            "meter_accuracy": result.validation.meter.accuracy,
            "rhyme_accuracy": result.validation.rhyme.accuracy,
            "feedback": format_all_feedback(
                formatter, result.validation.meter.feedback, result.validation.rhyme.feedback,
            ),
            "iterations": result.validation.iterations,
            "iteration_history": result.iteration_history,
            "iteration_displays": iteration_displays,
            "extra_metrics": extra_metrics,
        },
    )


@router.post("/validate-web", response_class=HTMLResponse)
def validate_web(
    request: Request,
    poem_text: str = Form(..., min_length=1),
    meter: str = Form("ямб"),
    feet: int = Form(4, ge=1, le=8),
    scheme: str = Form("ABAB"),
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
) -> HTMLResponse:
    try:
        val_request = ValidationRequest(
            poem_text=poem_text,
            meter=MeterSpec(name=meter, foot_count=feet),
            rhyme=RhymeScheme(pattern=scheme),
        )
        result = service.validate(val_request)
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": str(exc)},
        )
    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "poem": poem_text,
            "line_displays": _line_displays(poem_text, result.meter.line_results),
            "theme": "",
            "meter": meter,
            "feet": feet,
            "scheme": scheme,
            "is_valid": result.is_valid,
            "meter_ok": result.meter.ok,
            "rhyme_ok": result.rhyme.ok,
            "meter_accuracy": result.meter.accuracy,
            "rhyme_accuracy": result.rhyme.accuracy,
            "feedback": format_all_feedback(formatter, result.meter.feedback, result.rhyme.feedback),
        },
    )
