"""Detection orchestrator — shared between HTML and JSON API handlers.

Runs full-poem detection, splits into stanzas, resolves per-stanza meter
(full-poem → per-stanza → best-guess), and re-validates each stanza to
build annotated `line_displays`. Returns a structured `DetectionContext`
both handlers can render (one into Jinja templates, the other into JSON).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.domain.detection import MeterDetection, RhymeDetection
from src.domain.errors import DomainError
from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest
from src.domain.ports.validation import IMeterValidator, IRhymeValidator
from src.domain.values import MeterName
from src.handlers.shared.line_displays import line_displays
from src.services.detection_service import DetectionService
from src.services.poetry_service import PoetryService

_log = logging.getLogger(__name__)

STANZA_SIZE = 4

_CANONICAL_METERS: tuple[MeterName, ...] = (
    MeterName.IAMB,
    MeterName.TROCHEE,
    MeterName.DACTYL,
    MeterName.AMPHIBRACH,
    MeterName.ANAPEST,
)


@dataclass
class StanzaDetection:
    """Per-stanza detection result with annotated line displays."""
    meter: MeterDetection | None = None
    rhyme: RhymeDetection | None = None
    meter_accuracy: float | None = None
    rhyme_accuracy: float | None = None
    lines_count: int = 0
    line_displays: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DetectionContext:
    """Full result of orchestrated detection — enough to render both web and API views."""
    poem_text: str
    full_meter: MeterDetection | None
    full_rhyme: RhymeDetection | None
    is_detected: bool
    want_meter: bool
    want_rhyme: bool
    validated_lines: int
    stanzas: list[StanzaDetection]
    error: str | None = None


def split_stanzas(poem_text: str, stanza_size: int = STANZA_SIZE) -> list[str]:
    """Split poem into stanzas by blank lines, falling back to fixed-size chunks."""
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

    all_lines = [ln for ln in poem_text.splitlines() if ln.strip()]
    if len(all_lines) <= stanza_size:
        return stanzas

    chunks: list[str] = []
    for i in range(0, len(all_lines), stanza_size):
        chunk = all_lines[i : i + stanza_size]
        if chunk:
            chunks.append("\n".join(chunk))
    return chunks


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
    meter_validator: IMeterValidator,
) -> MeterDetection | None:
    if full_meter is not None:
        return full_meter
    try:
        stanza_result = service.detect(stanza_text, sample_lines=STANZA_SIZE)
        if stanza_result.meter is not None:
            return stanza_result.meter
    except DomainError:
        pass
    return _best_guess_meter(stanza_text, meter_validator)


def _stanza_rhyme_fits(
    stanza_text: str,
    rhyme: RhymeDetection,
    rhyme_validator: IRhymeValidator,
    threshold: float,
) -> bool:
    try:
        result = rhyme_validator.validate(
            stanza_text, RhymeScheme(pattern=rhyme.scheme),
        )
    except DomainError:
        return False
    return result.accuracy >= threshold


def _resolve_stanza_rhyme(
    stanza_text: str,
    full_rhyme: RhymeDetection | None,
    service: DetectionService,
    rhyme_validator: IRhymeValidator,
    rhyme_min_accuracy: float,
) -> RhymeDetection | None:
    """Pick the rhyme scheme for a stanza.

    Re-detects on the stanza when the inherited full-poem scheme scores
    below `rhyme_min_accuracy` for it — handles poems whose stanzas use
    different schemes (e.g. ABAB throughout but one AABB couplet stanza).
    """
    if full_rhyme is not None and _stanza_rhyme_fits(
        stanza_text, full_rhyme, rhyme_validator, rhyme_min_accuracy,
    ):
        return full_rhyme
    try:
        sr = service.detect(stanza_text, sample_lines=STANZA_SIZE)
        if sr.rhyme is not None:
            return sr.rhyme
    except DomainError:
        pass
    return full_rhyme


def _validate_stanza(
    stanza_text: str,
    meter: MeterSpec,
    rhyme_pattern: str,
    poetry: PoetryService,
) -> StanzaDetection:
    try:
        validation = poetry.validate(ValidationRequest(
            poem_text=stanza_text,
            meter=meter,
            rhyme=RhymeScheme(pattern=rhyme_pattern),
        ))
        return StanzaDetection(
            line_displays=line_displays(stanza_text, validation.meter.line_results),
            meter_accuracy=validation.meter.accuracy,
            rhyme_accuracy=validation.rhyme.accuracy,
            lines_count=len(validation.meter.line_results),
        )
    except DomainError as exc:
        _log.warning("Stanza validation failed: %s", exc)
        return _plain_stanza(stanza_text)


def _plain_stanza(stanza_text: str) -> StanzaDetection:
    lines = [ln for ln in stanza_text.splitlines() if ln.strip()]
    return StanzaDetection(
        line_displays=[
            {"blank": False, "text": ln.strip(), "segments": None}
            for ln in lines
        ],
        lines_count=len(lines),
    )


def detect_poem(
    poem_text: str,
    want_meter: bool,
    want_rhyme: bool,
    service: DetectionService,
    poetry: PoetryService,
    meter_validator: IMeterValidator,
    rhyme_validator: IRhymeValidator,
    rhyme_min_accuracy: float,
) -> DetectionContext:
    """Run the full detection flow and return a structured context.

    Raises nothing — request-validation errors (empty poem, non-multiple-of-4
    line count when rhyme is requested, neither aspect selected) are returned
    as a `DetectionContext` with `error` set so callers can render them.
    """
    if not want_meter and not want_rhyme:
        return DetectionContext(
            poem_text=poem_text, full_meter=None, full_rhyme=None,
            is_detected=False, want_meter=False, want_rhyme=False,
            validated_lines=0, stanzas=[],
            error="Оберіть хоча б один параметр для визначення: метр або схему римування.",
        )

    all_lines = [ln for ln in poem_text.splitlines() if ln.strip()]

    if not all_lines:
        return DetectionContext(
            poem_text=poem_text, full_meter=None, full_rhyme=None,
            is_detected=False, want_meter=want_meter, want_rhyme=want_rhyme,
            validated_lines=0, stanzas=[],
            error="Вірш не містить жодного рядка.",
        )

    if want_rhyme and len(all_lines) % STANZA_SIZE != 0:
        return DetectionContext(
            poem_text=poem_text, full_meter=None, full_rhyme=None,
            is_detected=False, want_meter=want_meter, want_rhyme=want_rhyme,
            validated_lines=0, stanzas=[],
            error=(
                f"Для визначення схеми римування кількість рядків "
                f"({len(all_lines)}) має бути кратною {STANZA_SIZE}."
            ),
        )

    # Full-poem detection (only requested aspects)
    full_meter: MeterDetection | None = None
    full_rhyme: RhymeDetection | None = None
    if want_meter and len(all_lines) >= STANZA_SIZE:
        try:
            full_result = service.detect(poem_text, sample_lines=STANZA_SIZE)
            full_meter = full_result.meter
            if want_rhyme:
                full_rhyme = full_result.rhyme
        except DomainError:
            pass
    elif want_meter:
        full_meter = _best_guess_meter(poem_text, meter_validator)

    if want_rhyme and full_rhyme is None and len(all_lines) >= STANZA_SIZE:
        try:
            rhyme_result = service.detect(poem_text, sample_lines=STANZA_SIZE)
            full_rhyme = rhyme_result.rhyme
        except DomainError:
            pass

    # Split into stanzas (for rhyme) or treat whole poem as one block (meter-only).
    stanzas_text = split_stanzas(poem_text) if want_rhyme else [poem_text]

    stanza_results: list[StanzaDetection] = []
    total_validated = 0

    for stanza_text in stanzas_text:
        meter_det: MeterDetection | None = None
        rhyme_det: RhymeDetection | None = None

        if want_meter:
            meter_det = _detect_meter_for_stanza(
                stanza_text, full_meter, service, meter_validator,
            )
        if want_rhyme:
            rhyme_det = _resolve_stanza_rhyme(
                stanza_text, full_rhyme, service,
                rhyme_validator, rhyme_min_accuracy,
            )

        if meter_det is not None:
            meter_spec = MeterSpec(name=meter_det.meter, foot_count=meter_det.foot_count)
            rhyme_pattern = rhyme_det.scheme if rhyme_det else "ABAB"
            stanza_info = _validate_stanza(stanza_text, meter_spec, rhyme_pattern, poetry)
            stanza_info.meter = meter_det
            stanza_info.rhyme = rhyme_det if want_rhyme else None
        else:
            stanza_info = _plain_stanza(stanza_text)

        total_validated += stanza_info.lines_count
        stanza_results.append(stanza_info)

    is_detected = (
        (not want_meter or full_meter is not None)
        and (not want_rhyme or full_rhyme is not None)
    )

    return DetectionContext(
        poem_text=poem_text,
        full_meter=full_meter,
        full_rhyme=full_rhyme,
        is_detected=is_detected,
        want_meter=want_meter,
        want_rhyme=want_rhyme,
        validated_lines=total_validated,
        stanzas=stanza_results,
    )
