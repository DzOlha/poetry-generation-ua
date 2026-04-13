"""Unit tests for SemanticRetriever."""
from __future__ import annotations

from src.domain.models import RetrievedExcerpt, ThemeExcerpt
from src.infrastructure.retrieval.semantic_retriever import SemanticRetriever


class TestSemanticRetriever:
    def test_encode_returns_list_of_floats(self, offline_embedder):
        vec = offline_embedder.encode("тестова тема")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        assert len(vec) > 0

    def test_retrieve_returns_items(self, offline_embedder, demo_corpus: list[ThemeExcerpt]):
        service = SemanticRetriever(offline_embedder)
        items = service.retrieve("весна у лісі", demo_corpus, top_k=2)
        assert isinstance(items, list)
        assert len(items) <= 2
        for item in items:
            assert isinstance(item, RetrievedExcerpt)
            assert isinstance(item.similarity, float)

    def test_retrieve_top_k_limit(self, offline_embedder, demo_corpus: list[ThemeExcerpt]):
        service = SemanticRetriever(offline_embedder)
        items = service.retrieve("тема", demo_corpus, top_k=1)
        assert len(items) == 1

    def test_retrieve_empty_corpus(self, offline_embedder):
        service = SemanticRetriever(offline_embedder)
        assert service.retrieve("тема", [], top_k=5) == []
