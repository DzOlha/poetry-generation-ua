"""Web UI — meter/rhyme detection routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.detection import MeterDetection, RhymeDetection
from src.domain.errors import DomainError
from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest
from src.domain.ports.validation import IMeterValidator
from src.domain.values import MeterName
from src.handlers.api.dependencies import get_detection_service, get_poetry_service
from src.handlers.web.routes._shared import templates
from src.handlers.web.routes.generation import _line_displays
from src.services.detection_service import DetectionService
from src.services.poetry_service import PoetryService

_log = logging.getLogger(__name__)

router = APIRouter()

_STANZA_SIZE = 4

_CANONICAL_METERS: tuple[MeterName, ...] = (
    MeterName.IAMB,
    MeterName.TROCHEE,
    MeterName.DACTYL,
    MeterName.AMPHIBRACH,
    MeterName.ANAPEST,
)


def _split_stanzas(poem_text: str, stanza_size: int) -> list[str]:
    """Split poem text into stanzas.

    First tries to split by blank lines. If the poem has no blank-line
    separators, falls back to splitting into chunks of ``stanza_size`` lines.
    """
    stanzas: list[str] = []
    current: list[str] = []
    has_blank_sep = False
    for line in poem_text.splitlines():
        if line.strip():
            current.append(line)
        else:
            if current:
                stanzas.append("\n".join(current))
                current = []
            has_blank_sep = True
    if current:
        stanzas.append("\n".join(current))

    if has_blank_sep or len(stanzas) != 1:
        return stanzas

    # No blank-line separators — split by stanza_size
    all_lines = [ln for ln in poem_text.splitlines() if ln.strip()]
    if len(all_lines) <= stanza_size:
        return stanzas

    chunks: list[str] = []
    for i in range(0, len(all_lines), stanza_size):
        chunk = all_lines[i : i + stanza_size]
        if chunk:
            chunks.append("\n".join(chunk))
    return chunks


def _count_lines(stanzas: list[str]) -> int:
    return sum(
        sum(1 for ln in st.splitlines() if ln.strip()) for st in stanzas
    )


def _best_guess_meter(
    text: str,
    meter_validator: IMeterValidator,
    feet_min: int = 2,
    feet_max: int = 6,
) -> MeterDetection | None:
    """Find the highest-accuracy meter match with no threshold cutoff."""
    best: MeterDetection | None = None
    for meter in _CANONICAL_METERS:
        for feet in range(feet_min, feet_max + 1):
            spec = MeterSpec(name=meter.value, foot_count=feet)
            result = meter_validator.validate(text, spec)
            if result.accuracy == 0.0:
                continue
            if best is None or result.accuracy > best.accuracy:
                best = MeterDetection(
                    meter=meter.value,
                    foot_count=feet,
                    accuracy=result.accuracy,
                )
    return best


def _detect_meter_for_stanza(
    stanza_text: str,
    full_meter: MeterDetection | None,
    service: DetectionService,
    request: Request,
) -> MeterDetection | None:
    """Resolve meter for a stanza: full-poem → per-stanza → best-guess."""
    if full_meter is not None:
        return full_meter
    try:
        stanza_result = service.detect(stanza_text, sample_lines=_STANZA_SIZE)
        if stanza_result.meter is not None:
            return stanza_result.meter
    except DomainError:
        pass
    meter_validator: IMeterValidator = request.app.state.container.meter_validator()
    return _best_guess_meter(stanza_text, meter_validator)


def _validate_stanza(
    stanza_text: str,
    meter: MeterSpec,
    rhyme_pattern: str,
    poetry: PoetryService,
) -> dict[str, object]:
    """Validate a single stanza and build its display dict."""
    try:
        validation = poetry.validate(ValidationRequest(
            poem_text=stanza_text,
            meter=meter,
            rhyme=RhymeScheme(pattern=rhyme_pattern),
        ))
        return {
            "line_displays": _line_displays(stanza_text, validation.meter.line_results),
            "meter_accuracy": validation.meter.accuracy,
            "rhyme_accuracy": validation.rhyme.accuracy,
            "lines_count": len(validation.meter.line_results),
        }
    except DomainError as exc:
        _log.warning("Stanza validation failed: %s", exc)
        return _plain_stanza(stanza_text)


def _plain_stanza(stanza_text: str) -> dict[str, object]:
    """Build a display dict with no highlighting."""
    lines = [ln for ln in stanza_text.splitlines() if ln.strip()]
    return {
        "line_displays": [
            {"blank": False, "text": ln.strip(), "segments": None}
            for ln in lines
        ],
        "meter_accuracy": None,
        "rhyme_accuracy": None,
        "lines_count": len(lines),
    }


@router.get("/detect", response_class=HTMLResponse)
def detect_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="detect.html", context={})


@router.post("/detect", response_class=HTMLResponse)
def detect_run(
    request: Request,
    poem_text: str = Form(..., min_length=1),
    detect_meter: str | None = Form(None),
    detect_rhyme: str | None = Form(None),
    service: DetectionService = Depends(get_detection_service),
    poetry: PoetryService = Depends(get_poetry_service),
) -> HTMLResponse:
    want_meter = detect_meter is not None
    want_rhyme = detect_rhyme is not None

    if not want_meter and not want_rhyme:
        return templates.TemplateResponse(
            request=request, name="error.html",
            context={"error": "Оберіть хоча б один параметр для визначення: метр або схему римування."},
        )

    all_lines = [ln for ln in poem_text.splitlines() if ln.strip()]

    if want_rhyme and len(all_lines) % _STANZA_SIZE != 0:
        return templates.TemplateResponse(
            request=request, name="error.html",
            context={
                "error": (
                    f"Для визначення схеми римування кількість рядків ({len(all_lines)}) "
                    f"має бути кратною {_STANZA_SIZE}."
                ),
            },
        )

    if not all_lines:
        return templates.TemplateResponse(
            request=request, name="error.html",
            context={"error": "Вірш не містить жодного рядка."},
        )

    # Run full-poem detection (only requested aspects)
    full_meter: MeterDetection | None = None
    full_rhyme: RhymeDetection | None = None
    if want_meter and len(all_lines) >= _STANZA_SIZE:
        try:
            full_result = service.detect(poem_text, sample_lines=_STANZA_SIZE)
            full_meter = full_result.meter
            if want_rhyme:
                full_rhyme = full_result.rhyme
        except DomainError:
            pass
    elif want_meter:
        # Fewer than 4 lines — meter-only, skip DetectionService sampler check
        meter_validator: IMeterValidator = request.app.state.container.meter_validator()
        full_meter = _best_guess_meter(poem_text, meter_validator)

    if want_rhyme and full_rhyme is None and len(all_lines) >= _STANZA_SIZE:
        try:
            rhyme_result = service.detect(poem_text, sample_lines=_STANZA_SIZE)
            full_rhyme = rhyme_result.rhyme
        except DomainError:
            pass

    # Split into stanzas (for rhyme) or treat whole poem as one block (meter-only)
    if want_rhyme:
        stanzas = _split_stanzas(poem_text, stanza_size=_STANZA_SIZE)
    else:
        stanzas = [poem_text]

    stanza_displays: list[dict[str, object]] = []
    total_validated = 0

    for stanza_text in stanzas:
        meter_det: MeterDetection | None = None
        rhyme_det: RhymeDetection | None = None

        if want_meter:
            meter_det = _detect_meter_for_stanza(
                stanza_text, full_meter, service, request,
            )

        if want_rhyme:
            rhyme_det = full_rhyme
            if rhyme_det is None:
                try:
                    sr = service.detect(stanza_text, sample_lines=_STANZA_SIZE)
                    rhyme_det = sr.rhyme
                except DomainError:
                    pass

        if meter_det is not None:
            meter_spec = MeterSpec(name=meter_det.meter, foot_count=meter_det.foot_count)
            rhyme_pattern = rhyme_det.scheme if rhyme_det else "ABAB"
            stanza_info = _validate_stanza(stanza_text, meter_spec, rhyme_pattern, poetry)
            stanza_info["meter"] = meter_det
            stanza_info["rhyme"] = rhyme_det if want_rhyme else None
        else:
            stanza_info = _plain_stanza(stanza_text)
            stanza_info["meter"] = None
            stanza_info["rhyme"] = None

        lines_count = stanza_info["lines_count"]
        assert isinstance(lines_count, int)
        total_validated += lines_count
        stanza_displays.append(stanza_info)

    is_detected = (
        (not want_meter or full_meter is not None)
        and (not want_rhyme or full_rhyme is not None)
    )

    return templates.TemplateResponse(
        request=request, name="detect_result.html", context={
            "poem_text": poem_text,
            "validated_lines": total_validated,
            "meter": full_meter if want_meter else None,
            "rhyme": full_rhyme if want_rhyme else None,
            "is_detected": is_detected,
            "want_meter": want_meter,
            "want_rhyme": want_rhyme,
            "stanzas": stanza_displays,
        },
    )
