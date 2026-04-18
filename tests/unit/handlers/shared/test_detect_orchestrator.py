"""Unit tests for the shared detection orchestrator.

The orchestrator runs detection, splits into stanzas, and re-validates each
stanza to build annotated displays. Web and API handlers both call it, so
it needs focused coverage — integration tests exercise only the happy path
through `/poems/detect` and can't assert on stanza-split edge cases,
best-guess fallback, or DomainError recovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.errors import UnsupportedConfigError
from src.domain.models import (
    LineMeterResult,
    MeterResult,
    MeterSpec,
    RhymeResult,
    ValidationRequest,
    ValidationResult,
)
from src.domain.ports.validation import IMeterValidator
from src.handlers.shared.detect_orchestrator import (
    DetectionContext,
    detect_poem,
    split_stanzas,
)
from src.services.detection_service import DetectionService
from src.services.poetry_service import PoetryService

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

@dataclass
class _FakeDetectionService:
    """Returns a scripted DetectionResult per call, or raises UnsupportedConfigError."""

    result: DetectionResult | None = None
    raise_error: bool = False
    calls: list[str] = field(default_factory=list)

    def detect(self, poem_text: str, *, sample_lines: int = 4) -> DetectionResult:
        self.calls.append(poem_text)
        if self.raise_error:
            raise UnsupportedConfigError("scripted failure")
        assert self.result is not None, "No scripted DetectionResult"
        return self.result


@dataclass
class _FakePoetryService:
    """Returns a scripted ValidationResult; records each validate() call."""

    validation: ValidationResult | None = None
    raise_error: bool = False
    calls: list[ValidationRequest] = field(default_factory=list)

    def validate(self, req: ValidationRequest) -> ValidationResult:
        self.calls.append(req)
        if self.raise_error:
            raise UnsupportedConfigError("scripted stanza failure")
        assert self.validation is not None
        return self.validation


class _FakeMeterValidator(IMeterValidator):
    """Returns `accuracy=best_accuracy` only for `(best_meter, best_feet)`, else 0.0."""

    def __init__(
        self,
        best_meter: str = "ямб",
        best_feet: int = 4,
        best_accuracy: float = 0.9,
    ) -> None:
        self._best_meter = best_meter
        self._best_feet = best_feet
        self._best_accuracy = best_accuracy

    def validate(self, text: str, meter: MeterSpec) -> MeterResult:
        if meter.name == self._best_meter and meter.foot_count == self._best_feet:
            return MeterResult(ok=True, accuracy=self._best_accuracy)
        return MeterResult(ok=False, accuracy=0.0)


def _valid_detection(meter: str = "ямб", feet: int = 4, scheme: str = "ABAB") -> DetectionResult:
    return DetectionResult(
        meter=MeterDetection(meter=meter, foot_count=feet, accuracy=0.95),
        rhyme=RhymeDetection(scheme=scheme, accuracy=1.0),
    )


def _valid_validation() -> ValidationResult:
    """Minimal ValidationResult that line_displays() can consume without failing."""
    line = LineMeterResult(
        ok=True,
        expected_stresses=(2, 4, 6, 8),
        actual_stresses=(2, 4, 6, 8),
        error_positions=(),
        total_syllables=8,
    )
    return ValidationResult(
        meter=MeterResult(ok=True, accuracy=1.0, line_results=(line,) * 4),
        rhyme=RhymeResult(ok=True, accuracy=1.0),
    )


def _run(
    poem_text: str,
    *,
    want_meter: bool = True,
    want_rhyme: bool = True,
    service: _FakeDetectionService | None = None,
    poetry: _FakePoetryService | None = None,
    meter_validator: IMeterValidator | None = None,
) -> DetectionContext:
    """Call detect_poem with casts — fakes duck-type the service classes."""
    return detect_poem(
        poem_text=poem_text,
        want_meter=want_meter,
        want_rhyme=want_rhyme,
        service=cast(DetectionService, service or _FakeDetectionService()),
        poetry=cast(PoetryService, poetry or _FakePoetryService()),
        meter_validator=meter_validator or _FakeMeterValidator(),
    )


# ---------------------------------------------------------------------------
# split_stanzas
# ---------------------------------------------------------------------------

class TestSplitStanzas:
    def test_blank_line_separator_preserves_groups(self) -> None:
        poem = "рядок перший\nрядок другий\n\nрядок третій\nрядок четвертий"
        assert split_stanzas(poem) == [
            "рядок перший\nрядок другий",
            "рядок третій\nрядок четвертий",
        ]

    def test_single_stanza_four_lines_stays_single(self) -> None:
        poem = "рядок перший\nрядок другий\nрядок третій\nрядок четвертий"
        # One stanza with exactly STANZA_SIZE (4) lines — no chunking triggered.
        assert split_stanzas(poem) == [poem]

    def test_eight_lines_without_blanks_are_chunked_by_stanza_size(self) -> None:
        # The UI accepts poems where the user forgot to separate stanzas; the
        # orchestrator must chunk into groups of 4 so rhyme extraction works.
        lines = [f"рядок номер {i}" for i in range(1, 9)]
        poem = "\n".join(lines)
        stanzas = split_stanzas(poem)
        assert len(stanzas) == 2
        assert stanzas[0].splitlines() == lines[:4]
        assert stanzas[1].splitlines() == lines[4:]

    def test_trailing_partial_chunk_kept(self) -> None:
        # 6 lines without blanks: chunks into 4 + 2.
        lines = [f"рядок {i}" for i in range(1, 7)]
        stanzas = split_stanzas("\n".join(lines))
        assert len(stanzas) == 2
        assert len(stanzas[1].splitlines()) == 2


# ---------------------------------------------------------------------------
# detect_poem — request-validation errors
# ---------------------------------------------------------------------------

class TestDetectPoemRequestValidation:
    def test_neither_aspect_selected_returns_error(self) -> None:
        ctx = _run("колосок", want_meter=False, want_rhyme=False)
        assert ctx.error is not None and "метр" in ctx.error
        assert ctx.stanzas == []

    def test_empty_poem_returns_error(self) -> None:
        ctx = _run("   \n\n\t\n")
        assert ctx.error is not None and "жодного рядка" in ctx.error

    def test_non_multiple_of_4_with_rhyme_returns_error(self) -> None:
        poem = "рядок перший\nрядок другий\nрядок третій"  # 3 lines
        ctx = _run(poem)
        assert ctx.error is not None and "кратною 4" in ctx.error

    def test_non_multiple_of_4_without_rhyme_is_ok(self) -> None:
        # Meter-only detection doesn't need stanza structure — 3 lines work.
        poem = (
            "рядок перший довгий\nрядок другий довгий\nрядок третій довгий\n"
        )
        ctx = _run(
            poem, want_rhyme=False,
            service=_FakeDetectionService(result=_valid_detection()),
            poetry=_FakePoetryService(validation=_valid_validation()),
        )
        assert ctx.error is None
        assert ctx.want_meter is True and ctx.want_rhyme is False


# ---------------------------------------------------------------------------
# detect_poem — happy path + edge-case orchestration
# ---------------------------------------------------------------------------

class TestDetectPoemOrchestration:
    def test_happy_path_full_meter_and_rhyme(self) -> None:
        poem = "\n".join([f"рядок {i} довгий" for i in range(1, 5)])
        ctx = _run(
            poem,
            service=_FakeDetectionService(result=_valid_detection("ямб", 4, "ABAB")),
            poetry=_FakePoetryService(validation=_valid_validation()),
        )
        assert ctx.is_detected is True
        assert ctx.full_meter is not None and ctx.full_meter.meter == "ямб"
        assert ctx.full_rhyme is not None and ctx.full_rhyme.scheme == "ABAB"
        assert len(ctx.stanzas) == 1
        # Stanza validation produced per-line displays with char-level segments.
        assert ctx.stanzas[0].meter_accuracy == 1.0
        assert ctx.stanzas[0].lines_count == 4

    def test_detection_service_error_falls_back_to_best_guess(self) -> None:
        # The DetectionService crashes, but the orchestrator should fall back
        # to the meter-validator-based best-guess so the user still gets a
        # partial result (meter only).
        poem = "рядок перший довгий\nрядок другий довгий\nрядок третій довгий\n"
        ctx = _run(
            poem, want_rhyme=False,
            service=_FakeDetectionService(raise_error=True),
            poetry=_FakePoetryService(validation=_valid_validation()),
            meter_validator=_FakeMeterValidator(
                best_meter="хорей", best_feet=3, best_accuracy=0.8,
            ),
        )
        assert ctx.full_meter is not None
        assert ctx.full_meter.meter == "хорей"
        assert ctx.full_meter.foot_count == 3

    def test_rhyme_only_skipped_when_not_requested(self) -> None:
        poem = "\n".join([f"рядок {i} довгий" for i in range(1, 5)])
        ctx = _run(
            poem, want_rhyme=False,
            service=_FakeDetectionService(result=_valid_detection()),
            poetry=_FakePoetryService(validation=_valid_validation()),
        )
        # Meter detected; rhyme intentionally not returned.
        assert ctx.full_meter is not None
        assert ctx.full_rhyme is None
        # The whole poem is treated as one block (not stanza-split) when rhyme
        # isn't requested — important so meter-only detection stays stable on
        # non-multiple-of-4 line counts.
        assert len(ctx.stanzas) == 1

    def test_stanza_validation_error_degrades_to_plain_stanza(self) -> None:
        # Stanza-level validation blowing up must not fail the whole run —
        # the orchestrator should return a plain text display for that stanza.
        poem = "\n".join([f"рядок {i} довгий" for i in range(1, 5)])
        ctx = _run(
            poem,
            service=_FakeDetectionService(result=_valid_detection()),
            poetry=_FakePoetryService(raise_error=True),
        )
        assert len(ctx.stanzas) == 1
        # No char-level highlights, just raw text lines.
        stanza = ctx.stanzas[0]
        assert stanza.meter_accuracy is None
        assert stanza.rhyme_accuracy is None
        assert all(d.get("segments") is None for d in stanza.line_displays)

    def test_is_detected_false_when_rhyme_missing_but_wanted(self) -> None:
        # DetectionService returns meter but no rhyme (degenerate poem).
        poem = "\n".join([f"рядок {i} довгий" for i in range(1, 5)])
        ctx = _run(
            poem,
            service=_FakeDetectionService(result=DetectionResult(
                meter=MeterDetection(meter="ямб", foot_count=4, accuracy=0.9),
                rhyme=None,
            )),
            poetry=_FakePoetryService(validation=_valid_validation()),
        )
        assert ctx.full_meter is not None
        assert ctx.full_rhyme is None
        assert ctx.is_detected is False

    def test_two_stanzas_accumulate_validated_lines(self) -> None:
        poem = "\n".join([f"рядок {i} довгий" for i in range(1, 9)])  # 8 lines
        ctx = _run(
            poem,
            service=_FakeDetectionService(result=_valid_detection()),
            poetry=_FakePoetryService(validation=_valid_validation()),
        )
        assert len(ctx.stanzas) == 2
        # Each stanza has 4 lines from our fake ValidationResult; 4 × 2 = 8.
        assert ctx.validated_lines == 8
