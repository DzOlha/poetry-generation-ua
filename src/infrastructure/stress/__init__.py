"""Stress / syllable adapters."""
from src.infrastructure.stress.penultimate_resolver import PenultimateFallbackStressResolver
from src.infrastructure.stress.syllable_counter import UkrainianSyllableCounter
from src.infrastructure.stress.ukrainian import UkrainianStressDict

__all__ = [
    "PenultimateFallbackStressResolver",
    "UkrainianStressDict",
    "UkrainianSyllableCounter",
]
