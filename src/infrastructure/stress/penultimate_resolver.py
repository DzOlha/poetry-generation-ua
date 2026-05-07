"""IStressResolver implementation with a linguistic fallback heuristic.

The dictionary engine answers when it can; otherwise we use a heuristic
based on the final segment of the word — a strong statistical predictor
of default stress in Ukrainian.

Heuristic layers, applied in order:
  1. Suffix rules — Ukrainian suffixes with highly consistent stress
     patterns override the generic fallback. Currently:
       * «-ота» (abstract feminine nouns) → last syllable
         (пустота́, німота́, самота́, красота́, сліпота́, доброта́).
  2. Generic final-segment rule:
       * ends in a vowel / «й» / «ь» → penultimate syllable,
       * ends in a hard consonant    → last syllable.

The generic rule outperforms a naive "always last syllable" baseline on
Ukrainian poetry vocabulary; the suffix rules correct the small but
systematically wrong slice where the generic rule picks the wrong syllable.
"""
from __future__ import annotations

from src.domain.ports import IStressDictionary, IStressResolver, ISyllableCounter
from src.shared.text_utils_ua import VOWELS_UA

# Characters treated as "soft" finals — these endings statistically
# correlate with penultimate stress in Ukrainian.
_SOFT_FINALS = frozenset(VOWELS_UA + "йь")

# Suffixes with highly consistent last-syllable stress. Each entry must
# only be added when nearly every Ukrainian word with that ending is
# last-stressed, so accuracy stays above the generic heuristic's baseline.
_SUFFIXES_LAST_STRESS: tuple[str, ...] = (
    "ота",  # пустота́, німота́, самота́, сліпота́, доброта́, красота́, теплота́
)
_MIN_SYLLABLES_FOR_SUFFIX_RULE = 3


class PenultimateFallbackStressResolver(IStressResolver):
    """Returns dictionary stress if available, else a heuristic guess.

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

        result = self._guess_stress(word)
        self._cache[word] = result
        return result

    def _guess_stress(self, word: str) -> int:
        n = self._syllables.count(word)
        if n <= 1:
            return 0
        lowered = word.lower()
        if n >= _MIN_SYLLABLES_FOR_SUFFIX_RULE:
            for suffix in _SUFFIXES_LAST_STRESS:
                if lowered.endswith(suffix):
                    return n - 1
        if lowered[-1] in _SOFT_FINALS:
            return max(0, n - 2)  # penultimate
        return n - 1              # last
