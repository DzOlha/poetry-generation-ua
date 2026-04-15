"""Web UI — meter/rhyme detection routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.errors import DomainError
from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest
from src.handlers.api.dependencies import get_detection_service, get_poetry_service
from src.handlers.web.routes._shared import templates
from src.handlers.web.routes.generation import _line_displays
from src.services.detection_service import DetectionService
from src.services.poetry_service import PoetryService

router = APIRouter()


@router.get("/detect", response_class=HTMLResponse)
def detect_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="detect.html", context={})


@router.post("/detect", response_class=HTMLResponse)
def detect_run(
    request: Request,
    poem_text: str = Form(..., min_length=1),
    sample_lines: int = Form(4, ge=2, le=14),
    service: DetectionService = Depends(get_detection_service),
    poetry: PoetryService = Depends(get_poetry_service),
) -> HTMLResponse:
    try:
        result = service.detect(poem_text, sample_lines=sample_lines)
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": str(exc)},
        )

    line_displays: list[dict[str, object]] = []
    if result.meter is not None:
        try:
            validation = poetry.validate(ValidationRequest(
                poem_text=poem_text,
                meter=MeterSpec(name=result.meter.meter, foot_count=result.meter.foot_count),
                rhyme=RhymeScheme(pattern=result.rhyme.scheme if result.rhyme else "ABAB"),
            ))
            line_displays = _line_displays(poem_text, validation.meter.line_results)
        except DomainError:
            line_displays = []

    return templates.TemplateResponse(
        request=request, name="detect_result.html", context={
            "poem_text": poem_text,
            "sample_lines": sample_lines,
            "result": result,
            "meter": result.meter,
            "rhyme": result.rhyme,
            "is_detected": result.is_detected,
            "line_displays": line_displays,
        },
    )
