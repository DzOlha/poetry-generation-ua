"""Rhyme-scheme extraction and pair analysis ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.value_objects import ClausulaType, RhymePrecision


class IRhymeSchemeExtractor(ABC):
    """Maps a rhyme-scheme pattern to concrete line-pair indices."""

    @abstractmethod
    def extract_pairs(self, scheme: str, n_lines: int) -> list[tuple[int, int]]: ...


@dataclass(frozen=True)
class RhymePairAnalysis:
    """Result of comparing the phonetic rhyme endings of two words."""

    rhyme_part_a: str
    rhyme_part_b: str
    score: float
    clausula_a: ClausulaType = ClausulaType.UNKNOWN
    clausula_b: ClausulaType = ClausulaType.UNKNOWN
    precision: RhymePrecision = RhymePrecision.NONE


class IRhymePairAnalyzer(ABC):
    """Computes the phonetic rhyme similarity between two line-final words."""

    @abstractmethod
    def analyze(self, word_a: str, word_b: str) -> RhymePairAnalysis: ...
