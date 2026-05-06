"""Meter/rhyme detection API route."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.config import DetectionConfig
from src.domain.ports.validation import IMeterValidator, IRhymeValidator
from src.handlers.api.dependencies import (
    get_detection_config,
    get_detection_service,
    get_meter_validator,
    get_poetry_service,
    get_rhyme_validator,
)
from src.handlers.api.schemas import (
    DetectionRequestSchema,
    DetectionResultSchema,
    LineDisplaySchema,
    MeterDetectionSchema,
    RhymeDetectionSchema,
    StanzaDetectionSchema,
)
from src.handlers.shared.detect_orchestrator import detect_poem
from src.services.detection_service import DetectionService
from src.services.poetry_service import PoetryService

router = APIRouter(prefix="/poems", tags=["poems"])


@router.post("/detect", response_model=DetectionResultSchema)
def detect_poem_endpoint(
    body: DetectionRequestSchema,
    service: DetectionService = Depends(get_detection_service),
    poetry: PoetryService = Depends(get_poetry_service),
    meter_validator: IMeterValidator = Depends(get_meter_validator),
    rhyme_validator: IRhymeValidator = Depends(get_rhyme_validator),
    detection_config: DetectionConfig = Depends(get_detection_config),
) -> DetectionResultSchema:
    """Auto-detect meter and rhyme scheme of a poem.

    Response includes per-stanza `line_displays` with char-level stress
    segments plus stanza-level accuracy — everything an SPA needs to render
    the same highlighted UI the HTML handler produces.
    """
    ctx = detect_poem(
        poem_text=body.poem_text,
        want_meter=body.detect_meter,
        want_rhyme=body.detect_rhyme,
        service=service,
        poetry=poetry,
        meter_validator=meter_validator,
        rhyme_validator=rhyme_validator,
        rhyme_min_accuracy=detection_config.rhyme_min_accuracy,
    )

    if ctx.error:
        raise HTTPException(status_code=422, detail=ctx.error)

    stanza_schemas = [
        StanzaDetectionSchema(
            meter=MeterDetectionSchema.from_domain(s.meter) if s.meter else None,
            rhyme=RhymeDetectionSchema.from_domain(s.rhyme) if s.rhyme else None,
            meter_accuracy=s.meter_accuracy,
            rhyme_accuracy=s.rhyme_accuracy,
            lines_count=s.lines_count,
            line_displays=[LineDisplaySchema.model_validate(d) for d in s.line_displays],
        )
        for s in ctx.stanzas
    ]

    return DetectionResultSchema(
        meter=(
            MeterDetectionSchema.from_domain(ctx.full_meter)
            if ctx.full_meter and ctx.want_meter else None
        ),
        rhyme=(
            RhymeDetectionSchema.from_domain(ctx.full_rhyme)
            if ctx.full_rhyme and ctx.want_rhyme else None
        ),
        is_detected=ctx.is_detected,
        poem_text=ctx.poem_text,
        validated_lines=ctx.validated_lines,
        want_meter=ctx.want_meter,
        want_rhyme=ctx.want_rhyme,
        stanzas=stanza_schemas,
    )
