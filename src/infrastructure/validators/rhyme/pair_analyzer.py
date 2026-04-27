"""`IRhymePairAnalyzer` implementation — phonetic rhyme similarity for Ukrainian.

Encapsulates the `stress resolver → transcriber → rhyme-part → similarity`
pipeline that used to live inline in `PhoneticRhymeValidator`. The validator
now depends on the narrow `IRhymePairAnalyzer` port plus line splitting,
tokenisation, and scheme extraction; all phonetic concerns are hidden here.

Extended with clausula detection (masculine/feminine/dactylic/hyperdactylic)
and rhyme precision classification (exact/assonance/consonance/inexact).
"""
from __future__ import annotations

from src.domain.ports import (
    IPhoneticTranscriber,
    IRhymePairAnalyzer,
    IStressResolver,
    IStringSimilarity,
    ISyllableCounter,
    RhymePairAnalysis,
)
from src.domain.value_objects import ClausulaType, RhymePrecision

# IPA vowels used to separate vowel/consonant channels for precision classification
_IPA_VOWELS: frozenset[str] = frozenset("aeiouɪ")

# Thresholds for rhyme precision classification
_EXACT_THRESHOLD: float = 0.95
_ASSONANCE_CONSONANCE_THRESHOLD: float = 0.75


class PhoneticRhymePairAnalyzer(IRhymePairAnalyzer):
    """Computes rhyme similarity via IPA rhyme-part extraction + Levenshtein score.

    When the stress dictionary is unavailable the resolver uses a heuristic
    that can be wrong. To compensate, the analyzer tries both the resolved
    stress position and the penultimate position (if different), picks the
    pair that yields the highest suffix-aligned similarity, and reports that.

    Additionally classifies:
    * **clausula** for each word (masculine / feminine / dactylic / hyperdactylic)
    * **rhyme precision** for the pair (exact / assonance / consonance / inexact)
    """

    def __init__(
        self,
        stress_resolver: IStressResolver,
        transcriber: IPhoneticTranscriber,
        string_similarity: IStringSimilarity,
        syllable_counter: ISyllableCounter | None = None,
    ) -> None:
        self._stress = stress_resolver
        self._transcriber = transcriber
        self._similarity = string_similarity
        self._syllables = syllable_counter

    def analyze(self, word_a: str, word_b: str) -> RhymePairAnalysis:
        candidates_a = self._rhyme_candidates(word_a)
        candidates_b = self._rhyme_candidates(word_b)

        best_score = -1.0
        best_r_a = ""
        best_r_b = ""

        for r_a in candidates_a:
            for r_b in candidates_b:
                if not self._stressed_syllables_align(r_a, r_b):
                    continue
                score = self._suffix_aligned_score(r_a, r_b)
                if score > best_score:
                    best_score, best_r_a, best_r_b = score, r_a, r_b

        if best_score < 0.0:
            # Every stress-candidate combination was gated out: the words
            # share only an unstressed suffix and do not rhyme. Surface the
            # canonical rhyme parts for diagnostics.
            final_score = 0.0
            precision = RhymePrecision.NONE
            if candidates_a and candidates_b:
                best_r_a = candidates_a[0]
                best_r_b = candidates_b[0]
        else:
            final_score = best_score
            precision = self._classify_precision(best_r_a, best_r_b, final_score)

        clausula_a = self._detect_clausula(word_a)
        clausula_b = self._detect_clausula(word_b)

        return RhymePairAnalysis(
            rhyme_part_a=best_r_a,
            rhyme_part_b=best_r_b,
            score=final_score,
            clausula_a=clausula_a,
            clausula_b=clausula_b,
            precision=precision,
        )

    def _stressed_syllables_align(self, r_a: str, r_b: str) -> bool:
        """Reject pairs that share only an unstressed grammatical suffix.

        Canonical rule of Ukrainian rhyme: the stressed vowel is the
        anchor. The pair is accepted when either
        * the stressed vowels match (exact / assonance / inexact rhyme), or
        * the stressed vowels differ but the consonants framing the
          stressed vowel match closely enough to qualify as consonance
          (e.g. «по́лем / до́лом», «гра́д / звід»).

        Returns False when both stressed vowels and stressed-syllable
        consonants differ — that is the «шибочках / кутиках» case where
        only the unstressed inflection «-ках» coincides.
        """
        if not r_a or not r_b:
            return True
        sv_a = _stressed_vowel(r_a)
        sv_b = _stressed_vowel(r_b)
        if not sv_a or not sv_b or sv_a == sv_b:
            return True
        cons_a = _stressed_syllable_consonants(r_a)
        cons_b = _stressed_syllable_consonants(r_b)
        if not cons_a or not cons_b:
            return False
        return self._similarity.similarity(cons_a, cons_b) >= _ASSONANCE_CONSONANCE_THRESHOLD

    # ------------------------------------------------------------------
    # Clausula detection
    # ------------------------------------------------------------------

    def _detect_clausula(self, word: str) -> ClausulaType:
        """Classify word ending by stress position relative to the last syllable.

        Counts the number of unstressed syllables after the stressed one:
        * 0 → masculine (чоловіча / окситонна)
        * 1 → feminine (жіноча / парокситонна)
        * 2 → dactylic (дактилічна)
        * 3+ → hyperdactylic (гіпердактилічна)
        """
        if not word:
            return ClausulaType.UNKNOWN

        n_syllables = self._count_syllables(word)
        if n_syllables == 0:
            return ClausulaType.UNKNOWN

        stressed_idx = self._stress.resolve(word)
        trailing = n_syllables - 1 - stressed_idx

        if trailing <= 0:
            return ClausulaType.MASCULINE
        if trailing == 1:
            return ClausulaType.FEMININE
        if trailing == 2:
            return ClausulaType.DACTYLIC
        return ClausulaType.HYPERDACTYLIC

    def _count_syllables(self, word: str) -> int:
        """Count syllables using the injected counter or transcriber vowel positions."""
        if self._syllables is not None:
            return self._syllables.count(word)
        ipa = self._transcriber.transcribe(word)
        return len(self._transcriber.vowel_positions(ipa))

    # ------------------------------------------------------------------
    # Rhyme precision classification
    # ------------------------------------------------------------------

    def _classify_precision(
        self, rhyme_a: str, rhyme_b: str, overall_score: float,
    ) -> RhymePrecision:
        """Classify the rhyme pair precision based on vowel/consonant channel analysis.

        * EXACT      — overall similarity >= 0.95 (повний збіг звуків)
        * ASSONANCE  — vowel similarity high, consonant similarity lower
        * CONSONANCE — consonant similarity high, vowel similarity lower
        * INEXACT    — partial match that is neither pure assonance nor consonance
        * NONE       — no meaningful similarity
        """
        if not rhyme_a or not rhyme_b:
            return RhymePrecision.NONE

        if overall_score >= _EXACT_THRESHOLD:
            return RhymePrecision.EXACT

        # Align by suffix (same as the main scoring)
        min_len = min(len(rhyme_a), len(rhyme_b))
        trimmed_a = rhyme_a[-min_len:]
        trimmed_b = rhyme_b[-min_len:]

        vowels_a = _extract_channel(trimmed_a, vowels=True)
        vowels_b = _extract_channel(trimmed_b, vowels=True)
        consonants_a = _extract_channel(trimmed_a, vowels=False)
        consonants_b = _extract_channel(trimmed_b, vowels=False)

        vowel_sim = self._similarity.similarity(vowels_a, vowels_b)
        consonant_sim = self._similarity.similarity(consonants_a, consonants_b)

        if vowel_sim >= _ASSONANCE_CONSONANCE_THRESHOLD and consonant_sim < _ASSONANCE_CONSONANCE_THRESHOLD:
            return RhymePrecision.ASSONANCE

        if consonant_sim >= _ASSONANCE_CONSONANCE_THRESHOLD and vowel_sim < _ASSONANCE_CONSONANCE_THRESHOLD:
            return RhymePrecision.CONSONANCE

        if overall_score > 0.0:
            return RhymePrecision.INEXACT

        return RhymePrecision.NONE

    # ------------------------------------------------------------------
    # Rhyme candidates & scoring (unchanged logic)
    # ------------------------------------------------------------------

    def _rhyme_candidates(self, word: str) -> list[str]:
        """Return rhyme-part candidates for different plausible stress positions."""
        resolved = self._stress.resolve(word)
        parts: list[str] = [self._transcriber.rhyme_part(word, resolved)]

        if self._syllables is not None:
            n = self._syllables.count(word)
            penultimate = max(0, n - 2)
            if penultimate != resolved:
                rp = self._transcriber.rhyme_part(word, penultimate)
                if rp and rp not in parts:
                    parts.append(rp)

        return parts

    def _suffix_aligned_score(self, r_a: str, r_b: str) -> float:
        """Score two rhyme parts by Levenshtein similarity over the full IPA.

        Both inputs already start at the stressed vowel, so a fair
        comparison aligns them from the *left* and uses the full length
        as the normalisation base. Length disparity (e.g. 8-char vs
        4-char rhyme parts from words with stress at different depths)
        therefore lowers the score, as it should — a real rhyme requires
        the post-stress sequences to roughly coincide. Stress uncertainty
        is handled separately by `_rhyme_candidates`, which offers the
        resolved and the penultimate stress positions as alternatives.
        """
        if not r_a or not r_b:
            return 0.0
        return self._similarity.similarity(r_a, r_b)


def _extract_channel(ipa: str, *, vowels: bool) -> str:
    """Extract only vowels or only consonants from an IPA string."""
    return "".join(ch for ch in ipa if (ch in _IPA_VOWELS) == vowels)


def _stressed_vowel(rhyme_part: str) -> str:
    """First IPA vowel in the rhyme part — the stressed vowel itself."""
    return next((c for c in rhyme_part if c in _IPA_VOWELS), "")


def _stressed_syllable_consonants(rhyme_part: str) -> str:
    """IPA consonants framing the stressed vowel.

    For polysyllabic clausulas this is the cluster between the stressed
    vowel and the next vowel (coda of the stressed syllable + onset of
    the next). For masculine clausulas (no following vowel) it is the
    full post-stress coda. Returns "" when no stressed vowel exists.
    """
    if not rhyme_part:
        return ""
    first_vowel_idx = next(
        (i for i, c in enumerate(rhyme_part) if c in _IPA_VOWELS), -1,
    )
    if first_vowel_idx == -1:
        return ""
    rest = rhyme_part[first_vowel_idx + 1:]
    next_vowel_idx = next(
        (i for i, c in enumerate(rest) if c in _IPA_VOWELS), -1,
    )
    return rest if next_vowel_idx == -1 else rest[:next_vowel_idx]
