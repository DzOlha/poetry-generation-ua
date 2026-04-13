"""Contract coverage for `OfflineDeterministicEmbedder`."""
from __future__ import annotations

from src.domain.ports import IEmbedder
from src.infrastructure.embeddings import OfflineDeterministicEmbedder
from src.infrastructure.logging import NullLogger
from tests.contracts.embedder_contract import IEmbedderContract


class TestOfflineEmbedderContract(IEmbedderContract):
    def _make_embedder(self) -> IEmbedder:
        return OfflineDeterministicEmbedder(logger=NullLogger())
