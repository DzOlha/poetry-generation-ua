"""Semantic embedding adapters."""
from src.infrastructure.embeddings.composite import CompositeEmbedder
from src.infrastructure.embeddings.labse import (
    LaBSEEmbedder,
    OfflineDeterministicEmbedder,
)

__all__ = [
    "CompositeEmbedder",
    "LaBSEEmbedder",
    "OfflineDeterministicEmbedder",
]
