"""IPoemValidator implementation composing meter + rhyme validators.

Previously `ValidationService` in the services layer. Moved to infrastructure
and behind the `IPoemValidator` port so PoetryService depends on the
abstraction — the audit flagged the old direct-class dependency as a DIP
violation.
"""
from __future__ import annotations

from src.domain.models import ValidationRequest, ValidationResult
from src.domain.ports import IMeterValidator, IPoemValidator, IRhymeValidator


class CompositePoemValidator(IPoemValidator):
    """Runs meter and rhyme validators in sequence and aggregates the result."""

    def __init__(
        self,
        meter_validator: IMeterValidator,
        rhyme_validator: IRhymeValidator,
    ) -> None:
        self._meter = meter_validator
        self._rhyme = rhyme_validator

    def validate(
        self,
        request: ValidationRequest,
        iterations: int = 0,
    ) -> ValidationResult:
        meter_result = self._meter.validate(request.poem_text, request.meter)
        rhyme_result = self._rhyme.validate(request.poem_text, request.rhyme)
        return ValidationResult(
            meter=meter_result,
            rhyme=rhyme_result,
            iterations=iterations,
        )
