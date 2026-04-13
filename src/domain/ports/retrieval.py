"""Retrieval ports."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import RetrievedExcerpt, ThemeExcerpt


class IRetriever(ABC):
    """Retrieves the most relevant excerpts for a query from a corpus.

    Concrete implementations pick their own ranking strategy (semantic
    embedding, BM25, hybrid) and may ignore `corpus` if they own the data
    source themselves.
    """

    @abstractmethod
    def retrieve(
        self,
        theme: str,
        corpus: list[ThemeExcerpt],
        top_k: int = 5,
    ) -> list[RetrievedExcerpt]: ...
