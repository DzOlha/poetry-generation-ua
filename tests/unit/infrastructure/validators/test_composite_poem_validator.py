"""Unit tests for CompositePoemValidator."""
from __future__ import annotations

from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest, ValidationResult
from src.infrastructure.validators import CompositePoemValidator


class TestCompositePoemValidator:
    def test_validate_returns_validation_result(self, meter_validator, rhyme_validator):
        validator = CompositePoemValidator(
            meter_validator=meter_validator,
            rhyme_validator=rhyme_validator,
        )
        request = ValidationRequest(
            poem_text=(
                "Весна прийшла у ліс зелений,\n"
                "Де тінь і світло гомонить.\n"
                "Мов сни, пливуть думки натхненні,\n"
                "І серце в тиші гомонить.\n"
            ),
            meter=MeterSpec("ямб", 4),
            rhyme=RhymeScheme("ABAB"),
        )
        result = validator.validate(request)
        assert isinstance(result, ValidationResult)

    def test_iterations_is_propagated(self, meter_validator, rhyme_validator):
        validator = CompositePoemValidator(
            meter_validator=meter_validator,
            rhyme_validator=rhyme_validator,
        )
        request = ValidationRequest(
            poem_text="рядок один\nрядок два\nрядок три\nрядок чотири\n",
            meter=MeterSpec("ямб", 4),
            rhyme=RhymeScheme("ABAB"),
        )
        result = validator.validate(request, iterations=5)
        assert result.iterations == 5
