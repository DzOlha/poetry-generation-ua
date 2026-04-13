"""IStressResolver implementation that falls back to the penultimate vowel.

The dictionary engine answers when it can; otherwise we use a deterministic
heuristic. Centralising the fallback in its own class lets validators depend
on a single `IStressResolver` interface and always receive an int back —
without the dictionary port leaking shared utility imports.
"""
from __future__ import annotations

from src.domain.ports import IStressDictionary, IStressResolver, ISyllableCounter


class PenultimateFallbackStressResolver(IStressResolver):
    """Returns dictionary stress if available, else max(0, syllables - 1).

    Results are cached per word so that repeated lookups (e.g. during
    brute-force meter detection) hit the expensive stress library only once.
    """

    def __init__(
        self,
        stress_dictionary: IStressDictionary,
        syllable_counter: ISyllableCounter,
    ) -> None:
        self._stress = stress_dictionary
        self._syllables = syllable_counter
        self._cache: dict[str, int] = {}

    def resolve(self, word: str) -> int:
        cached = self._cache.get(word)
        if cached is not None:
            return cached

        idx = self._stress.get_stress_index(word)
        if idx is not None:
            self._cache[word] = idx
            return idx

        result = max(0, self._syllables.count(word) - 1)
        self._cache[word] = result
        return result
