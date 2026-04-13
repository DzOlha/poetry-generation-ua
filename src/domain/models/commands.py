"""Command / request objects — input DTOs for services."""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.models.specifications import MeterSpec, PoemStructure, RhymeScheme


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


@dataclass(frozen=True)
class ValidationRequest:
    """Command object for poem validation."""

    poem_text: str
    meter: MeterSpec
    rhyme: RhymeScheme
