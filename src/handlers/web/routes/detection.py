"""Web UI — meter/rhyme detection routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.errors import DomainError
from src.handlers.api.dependencies import get_detection_service
from src.handlers.web.routes._shared import templates
from src.services.detection_service import DetectionService

router = APIRouter()


@router.get("/detect", response_class=HTMLResponse)
def detect_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="detect.html", context={})


@router.post("/detect", response_class=HTMLResponse)
def detect_run(
    request: Request,
    poem_text: str = Form(...),
    sample_lines: int = Form(4),
    service: DetectionService = Depends(get_detection_service),
) -> HTMLResponse:
    try:
        result = service.detect(poem_text, sample_lines=sample_lines)
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": str(exc)},
        )
    return templates.TemplateResponse(
        request=request, name="detect_result.html", context={
            "poem_text": poem_text,
            "sample_lines": sample_lines,
            "result": result,
            "meter": result.meter,
            "rhyme": result.rhyme,
            "is_detected": result.is_detected,
        },
    )
