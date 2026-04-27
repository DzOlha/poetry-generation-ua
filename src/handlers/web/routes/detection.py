"""Web UI — meter/rhyme detection routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.ports.validation import IMeterValidator
from src.handlers.api.dependencies import (
    get_detection_service,
    get_meter_validator,
    get_poetry_service,
)
from src.handlers.shared.detect_orchestrator import detect_poem
from src.handlers.web.routes._shared import templates
from src.services.detection_service import DetectionService
from src.services.poetry_service import PoetryService

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/detect", response_class=HTMLResponse)
def detect_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="detect.html", context={})


@router.post("/detect", response_class=HTMLResponse)
def detect_run(
    request: Request,
    poem_text: str = Form(..., min_length=1, max_length=5000),
    detect_meter: str | None = Form(None),
    detect_rhyme: str | None = Form(None),
    service: DetectionService = Depends(get_detection_service),
    poetry: PoetryService = Depends(get_poetry_service),
    meter_validator: IMeterValidator = Depends(get_meter_validator),
) -> HTMLResponse:
    want_meter = detect_meter is not None
    want_rhyme = detect_rhyme is not None

    ctx = detect_poem(
        poem_text=poem_text,
        want_meter=want_meter,
        want_rhyme=want_rhyme,
        service=service,
        poetry=poetry,
        meter_validator=meter_validator,
    )

    if ctx.error:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": ctx.error},
        )

    stanza_displays = [
        {
            "line_displays": s.line_displays,
            "meter_accuracy": s.meter_accuracy,
            "rhyme_accuracy": s.rhyme_accuracy,
            "lines_count": s.lines_count,
            "meter": s.meter,
            "rhyme": s.rhyme,
        }
        for s in ctx.stanzas
    ]

    return templates.TemplateResponse(
        request=request, name="detect_result.html", context={
            "poem_text": ctx.poem_text,
            "validated_lines": ctx.validated_lines,
            "meter": ctx.full_meter if ctx.want_meter else None,
            "rhyme": ctx.full_rhyme if ctx.want_rhyme else None,
            "is_detected": ctx.is_detected,
            "want_meter": ctx.want_meter,
            "want_rhyme": ctx.want_rhyme,
            "stanzas": stanza_displays,
        },
    )
