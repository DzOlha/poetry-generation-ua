"""Contract every `IEmbedder` implementation must satisfy."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from src.domain.ports import IEmbedder


class IEmbedderContract(ABC):
    """Every IEmbedder must satisfy these behavioural guarantees."""

    @abstractmethod
    def _make_embedder(self) -> IEmbedder:
        """Return a fresh embedder under test."""

    def test_encode_returns_non_empty_vector(self) -> None:
        vec = self._make_embedder().encode("весна у лісі")
        assert isinstance(vec, list)
        assert vec, "encode() must return a non-empty vector"
        assert all(isinstance(x, float) for x in vec)
        assert all(math.isfinite(x) for x in vec), (
            "encode() must not return NaN or infinities"
        )

    def test_encode_is_deterministic(self) -> None:
        embedder = self._make_embedder()
        vec_a = embedder.encode("тиха вода")
        vec_b = embedder.encode("тиха вода")
        assert vec_a == vec_b, "encode() must be deterministic on identical input"

    def test_encode_produces_stable_dimension(self) -> None:
        embedder = self._make_embedder()
        d1 = len(embedder.encode("перший текст"))
        d2 = len(embedder.encode("другий довший текст тут"))
        assert d1 == d2, "vector dimension must be constant across inputs"

    def test_encode_empty_string_returns_vector(self) -> None:
        """Empty input must still return a valid vector, not raise."""
        vec = self._make_embedder().encode("")
        assert isinstance(vec, list)
        assert all(math.isfinite(x) for x in vec)
