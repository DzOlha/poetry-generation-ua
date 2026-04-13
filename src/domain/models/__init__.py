"""Domain models — all value objects, entities, and DTOs for the poetry system.

Organised into focused modules:

  models.specifications — MeterSpec, RhymeScheme, PoemStructure
  models.commands       — GenerationRequest, ValidationRequest
  models.aggregates     — Poem
  models.results        — LineMeterResult, RhymePairResult, MeterResult,
                          RhymeResult, ValidationResult, GenerationResult
  models.entities       — ThemeExcerpt, MetricExample, MetricQuery,
                          RetrievedExcerpt, LineTokens

All names are re-exported here so ``from src.domain.models import X``
continues to work unchanged.
"""

# -- Value objects (must be imported before results to avoid circular import
# with src.domain.feedback which also depends on these enums) --
# -- Aggregates --
from src.domain.models.aggregates import Poem

# -- Commands --
from src.domain.models.commands import (
    GenerationRequest,
    ValidationRequest,
)

# -- Entities --
from src.domain.models.entities import (
    LineTokens,
    MetricExample,
    MetricQuery,
    RetrievedExcerpt,
    ThemeExcerpt,
)

# -- Results --
from src.domain.models.results import (
    GenerationResult,
    LineMeterResult,
    MeterResult,
    RhymePairResult,
    RhymeResult,
    ValidationResult,
)

# -- Specifications --
from src.domain.models.specifications import (
    MeterSpec,
    PoemStructure,
    RhymeScheme,
)
from src.domain.value_objects import ClausulaType, RhymePrecision

__all__ = [
    # Specifications
    "MeterSpec",
    "RhymeScheme",
    "PoemStructure",
    # Commands
    "GenerationRequest",
    "ValidationRequest",
    # Aggregates
    "Poem",
    # Results
    "LineMeterResult",
    "RhymePairResult",
    "MeterResult",
    "RhymeResult",
    "ValidationResult",
    "GenerationResult",
    # Value objects
    "ClausulaType",
    "RhymePrecision",
    # Entities
    "ThemeExcerpt",
    "MetricExample",
    "MetricQuery",
    "RetrievedExcerpt",
    "LineTokens",
]
