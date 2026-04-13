"""Poem generation and validation API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.ports import IFeedbackFormatter
from src.handlers.api.dependencies import get_feedback_formatter, get_poetry_service
from src.handlers.api.schemas import (
    GenerationRequestSchema,
    GenerationResultSchema,
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
) -> GenerationResultSchema:
    """Generate a Ukrainian poem satisfying the given meter and rhyme constraints."""
    result = service.generate(request.to_domain())
    meter_msgs, rhyme_msgs = _format_meter_feedback(
        formatter,
        result.validation.meter.feedback,
        result.validation.rhyme.feedback,
    )
    return GenerationResultSchema.from_strings(result, meter_msgs, rhyme_msgs)


@router.post("/validate", response_model=ValidationResultSchema)
def validate_poem(
    request: ValidationRequestSchema,
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
) -> ValidationResultSchema:
    """Validate an existing poem against meter and rhyme constraints."""
    result = service.validate(request.to_domain())
    meter_msgs, rhyme_msgs = _format_meter_feedback(
        formatter, result.meter.feedback, result.rhyme.feedback,
    )
    return ValidationResultSchema.from_strings(result, meter_msgs, rhyme_msgs)
