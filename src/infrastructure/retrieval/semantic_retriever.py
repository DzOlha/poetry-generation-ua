"""Semantic retriever — cosine similarity between theme embedding and corpus.
"""
from __future__ import annotations

import math

from src.domain.models import RetrievedExcerpt, ThemeExcerpt
from src.domain.ports import IEmbedder, IRetriever


class SemanticRetriever(IRetriever):
    """Retrieves the most thematically similar excerpts for a given query.

    Uses cosine similarity between the query embedding and pre-computed
    (or on-demand computed) excerpt embeddings.
    """

    def __init__(self, embedder: IEmbedder) -> None:
        self._embedder = embedder

    def retrieve(
        self,
        theme: str,
        corpus: list[ThemeExcerpt],
        top_k: int = 5,
    ) -> list[RetrievedExcerpt]:
        query_vec = self._embedder.encode(theme)
        ranked = sorted(
            (self._score(query_vec, excerpt) for excerpt in corpus),
            key=lambda x: x.similarity,
            reverse=True,
        )
        return ranked[: max(1, top_k)]

    def _score(self, query_vec: list[float], excerpt: ThemeExcerpt) -> RetrievedExcerpt:
        if excerpt.embedding:
            doc_vec = [float(x) for x in excerpt.embedding]
        else:
            doc_vec = self._embedder.encode(excerpt.text)
        similarity = self._cosine(query_vec, doc_vec)
        return RetrievedExcerpt(excerpt=excerpt, similarity=similarity)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        denom = norm_a * norm_b
        return float(dot / denom) if denom else 0.0
