"""Default syllable flag strategy.

Builds per-syllable (is_monosyllabic, is_weak_stress_word) flag tuples by
delegating word-level lookups to an injected weak-stress lexicon.
"""
from __future__ import annotations

from src.domain.ports import ISyllableFlagStrategy, IWeakStressLexicon


class DefaultSyllableFlagStrategy(ISyllableFlagStrategy):
    """Per-syllable flagging that uses an IWeakStressLexicon for weak-word checks."""

    def __init__(self, weak_stress_lexicon: IWeakStressLexicon) -> None:
        self._weak = weak_stress_lexicon

    def flags(
        self,
        words: list[str],
        syllables_per_word: list[int],
    ) -> list[tuple[bool, bool]]:
        out: list[tuple[bool, bool]] = []
        for w, syl in zip(words, syllables_per_word):
            if syl <= 0:
                continue
            is_mono = syl == 1
            is_weak = self._weak.is_weak(w)
            out.extend([(is_mono, is_weak)] * syl)
        return out
