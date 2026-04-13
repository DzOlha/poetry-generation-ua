"""Validation ports."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import (
    MeterResult,
    MeterSpec,
    RhymeResult,
    RhymeScheme,
    ValidationRequest,
    ValidationResult,
)


class IMeterValidator(ABC):
    """Validates the metrical structure of poetry."""

    @abstractmethod
    def validate(self, poem_text: str, meter: MeterSpec) -> MeterResult: ...


class IRhymeValidator(ABC):
    """Validates the rhyme scheme of poetry."""

    @abstractmethod
    def validate(self, poem_text: str, scheme: RhymeScheme) -> RhymeResult: ...


class IPoemValidator(ABC):
    """Coordinates meter + rhyme validation, producing a combined result."""

    @abstractmethod
    def validate(
        self,
        request: ValidationRequest,
        iterations: int = 0,
    ) -> ValidationResult: ...
