"""Poem generation and validation API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.config import LLMInfo
from src.domain.errors import DomainError
from src.domain.evaluation import IterationRecord
from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.models import ValidationRequest
from src.domain.ports import (
    EvaluationContext,
    IFeedbackFormatter,
    IMetricCalculatorRegistry,
)
from src.handlers.api.dependencies import (
    get_feedback_formatter,
    get_llm_info,
    get_metric_registry,
    get_poetry_service,
)
from src.handlers.api.schemas import (
    GenerationRequestSchema,
    GenerationResultSchema,
    LineDisplaySchema,
    ValidationRequestSchema,
    ValidationResultSchema,
)
from src.services.poetry_service import PoetryService

router = APIRouter(prefix="/poems", tags=["poems"])


def _format_meter_feedback(
    formatter: IFeedbackFormatter,
    meter_fbs: tuple[LineFeedback, ...],
    rhyme_fbs: tuple[PairFeedback, ...],
) -> tuple[list[str], list[str]]:
    """Split the feedback formatting the router used to do in schemas."""
    meter_msgs = [formatter.format_line(f) for f in meter_fbs]
    rhyme_msgs = [formatter.format_pair(f) for f in rhyme_fbs]
    return meter_msgs, rhyme_msgs


@router.post("/generate", response_model=GenerationResultSchema)
def generate_poem(
    request: GenerationRequestSchema,
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
    metric_registry: IMetricCalculatorRegistry = Depends(get_metric_registry),
    llm_info: LLMInfo = Depends(get_llm_info),
) -> GenerationResultSchema:
    """Generate a Ukrainian poem satisfying the given meter and rhyme constraints.

    Response includes char-level stress segments (`validation.line_displays`),
    per-iteration annotated snapshots (`iteration_history[*].line_displays`),
    and server-computed metrics (`extra_metrics`) so an SPA can render the
    same UI as the HTML handler without recomputing stress positions.
    """
    if not llm_info.ready:
        # 503 Service Unavailable: the pipeline itself is fine but its LLM
        # dependency isn't configured (e.g. GEMINI_API_KEY missing).
        raise HTTPException(status_code=503, detail=llm_info.error)
    gen_request = request.to_domain()
    result = service.generate(gen_request)
    meter_msgs, rhyme_msgs = _format_meter_feedback(
        formatter,
        result.validation.meter.feedback,
        result.validation.rhyme.feedback,
    )

    # Build extra_metrics via the injected registry (same logic the web uses).
    iter_records = tuple(
        IterationRecord(
            iteration=s.iteration,
            poem_text=s.poem,
            meter_accuracy=s.meter_accuracy,
            rhyme_accuracy=s.rhyme_accuracy,
            feedback=tuple(s.feedback),
            duration_sec=s.duration_sec,
            raw_llm_response=s.raw_llm_response,
            sanitized_llm_response=s.sanitized_llm_response,
        )
        for s in result.iteration_history
    )
    ctx = EvaluationContext(
        poem_text=result.poem,
        meter=gen_request.meter,
        rhyme=gen_request.rhyme,
        iterations=list(iter_records),
        theme=gen_request.theme,
    )
    extra_metrics = {c.name: float(c.calculate(ctx)) for c in metric_registry.all()}

    # Re-validate each iteration snapshot to compute per-iteration line_displays.
    # Validation failure on a single snapshot falls back to an empty list so the
    # SPA can still render the rest (meter accuracy, feedback) for that entry.
    iteration_displays: list[list[LineDisplaySchema]] = []
    for snap in result.iteration_history:
        try:
            snap_val = service.validate(ValidationRequest(
                poem_text=snap.poem,
                meter=gen_request.meter,
                rhyme=gen_request.rhyme,
            ))
            iteration_displays.append(LineDisplaySchema.list_from(
                snap.poem, snap_val.meter.line_results,
            ))
        except DomainError:
            iteration_displays.append([])

    return GenerationResultSchema.from_strings(
        result, meter_msgs, rhyme_msgs,
        theme=gen_request.theme,
        extra_metrics=extra_metrics,
        iteration_displays=iteration_displays,
    )


@router.post("/validate", response_model=ValidationResultSchema)
def validate_poem(
    request: ValidationRequestSchema,
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
) -> ValidationResultSchema:
    """Validate an existing poem against meter and rhyme constraints.

    Response includes `line_displays` — char-level stress tagging per line —
    so an SPA can render the highlighted poem identical to the web UI.
    """
    val_request = request.to_domain()
    result = service.validate(val_request)
    meter_msgs, rhyme_msgs = _format_meter_feedback(
        formatter, result.meter.feedback, result.rhyme.feedback,
    )
    return ValidationResultSchema.from_strings(
        result, meter_msgs, rhyme_msgs, poem_text=val_request.poem_text,
    )
