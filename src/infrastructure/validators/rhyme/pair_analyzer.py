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
                score = self._suffix_aligned_score(r_a, r_b)
                if score > best_score:
                    best_score, best_r_a, best_r_b = score, r_a, r_b

        final_score = max(best_score, 0.0)

        clausula_a = self._detect_clausula(word_a)
        clausula_b = self._detect_clausula(word_b)
        precision = self._classify_precision(best_r_a, best_r_b, final_score)

        return RhymePairAnalysis(
            rhyme_part_a=best_r_a,
            rhyme_part_b=best_r_b,
            score=final_score,
            clausula_a=clausula_a,
            clausula_b=clausula_b,
            precision=precision,
        )

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
        """Compare rhyme parts aligned by suffix.

        When stress is uncertain the longer rhyme part may capture too
        much of the word.  Trimming both parts to the length of the
        shorter one (from the right) before comparing gives a fairer
        score while still relying on the injected similarity metric.
        """
        if not r_a or not r_b:
            return 0.0
        min_len = min(len(r_a), len(r_b))
        trimmed_a = r_a[-min_len:]
        trimmed_b = r_b[-min_len:]
        return self._similarity.similarity(trimmed_a, trimmed_b)


def _extract_channel(ipa: str, *, vowels: bool) -> str:
    """Extract only vowels or only consonants from an IPA string."""
    return "".join(ch for ch in ipa if (ch in _IPA_VOWELS) == vowels)
