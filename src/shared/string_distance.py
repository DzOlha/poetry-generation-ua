"""Pure edit-distance math — a genuine free-function utility.

No language assumptions, no extension points. Used by `UkrainianTextProcessor`
to implement `IStringSimilarity.similarity`; tests may import the functions
directly since they have no role that could reasonably change.
"""
from __future__ import annotations


def levenshtein_distance(a: str, b: str) -> int:
    """Classic Levenshtein edit distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(
                current[j - 1] + 1,
                previous[j] + 1,
                previous[j - 1] + (0 if ca == cb else 1),
            ))
        previous = current
    return previous[-1]


def normalized_similarity(a: str, b: str) -> float:
    """Normalized similarity in [0, 1]: 1 − (edit_distance / max_length)."""
    if not a and not b:
        return 1.0
    denom = max(len(a), len(b))
    if denom == 0:
        return 1.0
    return 1.0 - levenshtein_distance(a, b) / denom
