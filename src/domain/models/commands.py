"""Command / request objects — input DTOs for services."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors import UnsupportedConfigError
from src.domain.models.specifications import MeterSpec, PoemStructure, RhymeScheme


def _require_bounded_int(name: str, value: int, lo: int, hi: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise UnsupportedConfigError(
            f"{name} must be an integer, got {type(value).__name__}"
        )
    if not lo <= value <= hi:
        raise UnsupportedConfigError(f"{name} must be in [{lo}, {hi}], got {value}")


@dataclass(frozen=True)
class GenerationRequest:
    """Command object for poem generation — replaces long parameter lists."""

    theme: str
    meter: MeterSpec
    rhyme: RhymeScheme
    structure: PoemStructure
    max_iterations: int = 3
    top_k: int = 5
    metric_examples_top_k: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.theme, str) or not self.theme.strip():
            raise UnsupportedConfigError("theme must be a non-empty string")
        _require_bounded_int("max_iterations", self.max_iterations, 0, 10)
        _require_bounded_int("top_k", self.top_k, 1, 20)
        _require_bounded_int("metric_examples_top_k", self.metric_examples_top_k, 0, 10)


@dataclass(frozen=True)
class ValidationRequest:
    """Command object for poem validation."""

    poem_text: str
    meter: MeterSpec
    rhyme: RhymeScheme

    def __post_init__(self) -> None:
        if not isinstance(self.poem_text, str) or not self.poem_text.strip():
            raise UnsupportedConfigError("poem_text must be a non-empty string")
