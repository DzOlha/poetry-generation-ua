"""Contract every ``IPoemValidator`` implementation must satisfy."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest, ValidationResult
from src.domain.ports import IPoemValidator


class IPoemValidatorContract(ABC):
    """Every IPoemValidator must satisfy these behavioural guarantees."""

    @abstractmethod
    def _make_validator(self) -> IPoemValidator:
        """Return a fresh validator under test."""

    @staticmethod
    def _sample_request(poem: str = "") -> ValidationRequest:
        return ValidationRequest(
            poem_text=poem or (
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        )

    def test_validate_returns_validation_result(self) -> None:
        validator = self._make_validator()
        result = validator.validate(self._sample_request())
        assert isinstance(result, ValidationResult)

    def test_meter_accuracy_in_range(self) -> None:
        result = self._make_validator().validate(self._sample_request())
        assert 0.0 <= result.meter.accuracy <= 1.0

    def test_rhyme_accuracy_in_range(self) -> None:
        result = self._make_validator().validate(self._sample_request())
        assert 0.0 <= result.rhyme.accuracy <= 1.0

    def test_empty_poem_returns_result(self) -> None:
        result = self._make_validator().validate(self._sample_request(poem=""))
        assert isinstance(result, ValidationResult)

    def test_single_line_poem(self) -> None:
        result = self._make_validator().validate(
            self._sample_request(poem="Весна прийшла у ліс зелений"),
        )
        assert isinstance(result, ValidationResult)
