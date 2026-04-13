"""Tests for `CompositeEmbedder` — contract conformance + fallback behaviour."""
from __future__ import annotations

from src.domain.errors import EmbedderError
from src.domain.ports import IEmbedder
from src.infrastructure.embeddings import (
    CompositeEmbedder,
    OfflineDeterministicEmbedder,
)
from src.infrastructure.logging import NullLogger
from tests.contracts.embedder_contract import IEmbedderContract
from tests.fixtures.infrastructure import RecordingLogger


class _StaticVectorEmbedder(IEmbedder):
    def __init__(self, vec: list[float]) -> None:
        self._vec = list(vec)
        self.calls: int = 0

    def encode(self, text: str) -> list[float]:
        self.calls += 1
        return list(self._vec)


class _AlwaysFailsEmbedder(IEmbedder):
    def __init__(self) -> None:
        self.calls: int = 0

    def encode(self, text: str) -> list[float]:
        self.calls += 1
        raise EmbedderError("simulated failure")


class TestCompositeEmbedderContract(IEmbedderContract):
    """`CompositeEmbedder` must satisfy the IEmbedder contract when its primary works."""

    def _make_embedder(self) -> IEmbedder:
        return CompositeEmbedder(
            primary=OfflineDeterministicEmbedder(logger=NullLogger()),
            fallback=OfflineDeterministicEmbedder(logger=NullLogger()),
            logger=NullLogger(),
        )


class TestCompositeEmbedderFallback:
    def test_primary_success_is_returned(self) -> None:
        primary = _StaticVectorEmbedder([1.0, 2.0, 3.0])
        fallback = _StaticVectorEmbedder([9.0, 9.0, 9.0])
        composite = CompositeEmbedder(primary, fallback, NullLogger())
        assert composite.encode("x") == [1.0, 2.0, 3.0]
        assert primary.calls == 1
        assert fallback.calls == 0

    def test_primary_failure_switches_to_fallback(self) -> None:
        primary = _AlwaysFailsEmbedder()
        fallback = _StaticVectorEmbedder([7.0, 8.0])
        logger = RecordingLogger()
        composite = CompositeEmbedder(primary, fallback, logger)
        assert composite.encode("x") == [7.0, 8.0]
        assert fallback.calls == 1
        # Subsequent calls skip the primary entirely — no re-tries of the broken model.
        assert composite.encode("y") == [7.0, 8.0]
        assert primary.calls == 1
        assert fallback.calls == 2
        # Failure was logged exactly once.
        assert len(logger.warnings) == 1
