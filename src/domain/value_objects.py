"""Domain-level value objects and enumerations for rhyme classification."""
from __future__ import annotations

from enum import Enum


class ClausulaType(Enum):
    """Line-ending stress classification (клаузула).

    Determined by the number of unstressed syllables after the last
    stressed syllable in the rhyming word:

    * MASCULINE  (чоловіча / окситонна)   — 0 trailing unstressed
    * FEMININE   (жіноча / парокситонна)   — 1 trailing unstressed
    * DACTYLIC   (дактилічна)              — 2 trailing unstressed
    * HYPERDACTYLIC (гіпердактилічна)      — 3+ trailing unstressed
    """

    MASCULINE = "masculine"
    FEMININE = "feminine"
    DACTYLIC = "dactylic"
    HYPERDACTYLIC = "hyperdactylic"
    UNKNOWN = "unknown"


class RhymePrecision(Enum):
    """Rhyme precision classification (точність рими).

    * EXACT      (точна)       — full sound match from stressed vowel onward
    * ASSONANCE  (асонансна)   — vowels match, consonants differ
    * CONSONANCE (консонансна) — consonants match, vowels differ
    * INEXACT    (неточна)     — partial match, neither pure assonance nor consonance
    * NONE                     — no rhyme detected (score below threshold)
    """

    EXACT = "exact"
    ASSONANCE = "assonance"
    CONSONANCE = "consonance"
    INEXACT = "inexact"
    NONE = "none"
