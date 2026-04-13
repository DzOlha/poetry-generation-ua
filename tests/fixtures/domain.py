"""Domain-level fixtures — requests, sample poems, constants."""
from __future__ import annotations

import pytest

from src.domain.models import (
    GenerationRequest,
    MeterSpec,
    PoemStructure,
    RhymeScheme,
)


@pytest.fixture
def iamb_4ft_abab() -> GenerationRequest:
    """Standard 4-foot iamb + ABAB request used across many tests."""
    return GenerationRequest(
        theme="весна у лісі",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
        max_iterations=1,
    )
