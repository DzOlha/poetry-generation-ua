"""Semantic relevance metric calculator."""
from __future__ import annotations

import math

from src.domain.errors import EmbedderError
from src.domain.ports import EvaluationContext, IEmbedder, ILogger, IMetricCalculator


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two dense vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticRelevanceCalculator(IMetricCalculator):
    """Measures semantic similarity between the generated poem and the theme.

    The embedder is injected into the calculator itself (DIP); the context
    only carries domain inputs (theme, poem text, etc.). On EmbedderError
    the calculator returns 0.0 and logs a warning — production runs should
    be surprised by a warning, not silently corrupted results.
    """

    def __init__(self, embedder: IEmbedder, logger: ILogger) -> None:
        self._embedder = embedder
        self._logger: ILogger = logger

    @property
    def name(self) -> str:
        return "semantic_relevance"

    def calculate(self, context: EvaluationContext) -> float:
        if not context.theme or not context.poem_text:
            return 0.0
        try:
            theme_vec = self._embedder.encode(context.theme)
            poem_vec = self._embedder.encode(context.poem_text)
            return float(_cosine_similarity(theme_vec, poem_vec))
        except EmbedderError as exc:
            self._logger.warning(
                "SemanticRelevanceCalculator embedder unavailable",
                error=str(exc),
            )
            return 0.0
