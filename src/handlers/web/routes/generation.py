"""Web UI — poem generation and validation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.errors import DomainError
from src.domain.models import (
    GenerationRequest,
    MeterSpec,
    PoemStructure,
    RhymeScheme,
    ValidationRequest,
)
from src.domain.ports import IFeedbackFormatter, format_all_feedback
from src.handlers.api.dependencies import get_feedback_formatter, get_poetry_service
from src.handlers.web.routes._shared import templates
from src.services.poetry_service import PoetryService

router = APIRouter()


@router.post("/generate", response_class=HTMLResponse)
def generate_web(
    request: Request,
    theme: str = Form(...),
    meter: str = Form("ямб"),
    feet: int = Form(4),
    scheme: str = Form("ABAB"),
    stanzas: int = Form(4),
    lines: int = Form(4),
    iterations: int = Form(3),
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
) -> HTMLResponse:
    gen_request = GenerationRequest(
        theme=theme,
        meter=MeterSpec(name=meter, foot_count=feet),
        rhyme=RhymeScheme(pattern=scheme),
        structure=PoemStructure(stanza_count=stanzas, lines_per_stanza=lines),
        max_iterations=iterations,
    )
    try:
        result = service.generate(gen_request)
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": str(exc)},
        )
    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "poem": result.poem,
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
        },
    )


@router.post("/validate-web", response_class=HTMLResponse)
def validate_web(
    request: Request,
    poem_text: str = Form(...),
    meter: str = Form("ямб"),
    feet: int = Form(4),
    scheme: str = Form("ABAB"),
    service: PoetryService = Depends(get_poetry_service),
    formatter: IFeedbackFormatter = Depends(get_feedback_formatter),
) -> HTMLResponse:
    val_request = ValidationRequest(
        poem_text=poem_text,
        meter=MeterSpec(name=meter, foot_count=feet),
        rhyme=RhymeScheme(pattern=scheme),
    )
    try:
        result = service.validate(val_request)
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="error.html", context={"error": str(exc)},
        )
    return templates.TemplateResponse(
        request=request, name="result.html", context={
            "poem": poem_text,
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
            "iterations": result.iterations,
        },
    )
