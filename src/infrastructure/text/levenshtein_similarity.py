"""IStringSimilarity adapter backed by Levenshtein edit distance.

Separated from UkrainianTextProcessor to respect ISP: callers that only
need string similarity (e.g. the rhyme pair analyzer) no longer pull in
the full text-processing dependency graph.
"""
from __future__ import annotations

from src.domain.ports import IStringSimilarity
from src.shared.string_distance import normalized_similarity


class LevenshteinSimilarity(IStringSimilarity):
    """Normalised Levenshtein similarity in [0, 1]."""

    def similarity(self, a: str, b: str) -> float:
        return normalized_similarity(a, b)
