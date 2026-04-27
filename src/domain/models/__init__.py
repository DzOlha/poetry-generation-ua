"""Domain models — all value objects, entities, and DTOs for the poetry system.

Organised into focused modules:

  models.specifications      — MeterSpec, RhymeScheme, PoemStructure
  models.commands            — GenerationRequest, ValidationRequest
  models.aggregates          — Poem
  models.results             — LineMeterResult, RhymePairResult, MeterResult,
                               RhymeResult, ValidationResult, GenerationResult
  models.entities            — ThemeExcerpt, MetricExample, MetricQuery,
                               RetrievedExcerpt, LineTokens
  models.feedback            — LineFeedback, PairFeedback (structured violations)
  models.corpus_entry        — CorpusEntry typed dict
  models.metric_corpus_entry — MetricCorpusEntry typed dict

All names are re-exported here so ``from src.domain.models import X``
continues to work unchanged.
"""

# -- Aggregates --
from src.domain.models.aggregates import Poem

# -- Commands --
from src.domain.models.commands import (
    GenerationRequest,
    ValidationRequest,
)

# -- Corpus entries (typed dicts for JSON corpus shapes) --
from src.domain.models.corpus_entry import CorpusEntry

# -- Entities --
from src.domain.models.entities import (
    LineTokens,
    MetricExample,
    MetricQuery,
    RetrievedExcerpt,
    ThemeExcerpt,
)

# -- Feedback (structured validator violations) --
from src.domain.models.feedback import (
    LineFeedback,
    PairFeedback,
    format_all_feedback,
)

# -- Metric corpus entry --
from src.domain.models.metric_corpus_entry import MetricCorpusEntry

# -- Results --
from src.domain.models.results import (
    GenerationResult,
    IterationSnapshot,
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
    "IterationSnapshot",
    # Value objects
    "ClausulaType",
    "RhymePrecision",
    # Entities
    "ThemeExcerpt",
    "MetricExample",
    "MetricQuery",
    "RetrievedExcerpt",
    "LineTokens",
    # Feedback
    "LineFeedback",
    "PairFeedback",
    "format_all_feedback",
    # Corpus entries
    "CorpusEntry",
    "MetricCorpusEntry",
]
