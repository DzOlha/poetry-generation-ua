"""Tests for `PhoneticRhymePairAnalyzer`."""
from __future__ import annotations

from src.domain.ports import IStressDictionary
from src.domain.value_objects import ClausulaType, RhymePrecision
from src.infrastructure.phonetics import UkrainianIpaTranscriber
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianSyllableCounter,
)
from src.infrastructure.text import LevenshteinSimilarity
from src.infrastructure.validators.rhyme.pair_analyzer import PhoneticRhymePairAnalyzer


def _make(stress_dict: IStressDictionary) -> PhoneticRhymePairAnalyzer:
    syllable_counter = UkrainianSyllableCounter()
    return PhoneticRhymePairAnalyzer(
        stress_resolver=PenultimateFallbackStressResolver(
            stress_dictionary=stress_dict,
            syllable_counter=syllable_counter,
        ),
        transcriber=UkrainianIpaTranscriber(),
        string_similarity=LevenshteinSimilarity(),
        syllable_counter=syllable_counter,
    )


class TestPhoneticRhymePairAnalyzer:
    def test_identical_words_perfect_score(
        self, stress_dict: IStressDictionary,
    ) -> None:
        analysis = _make(stress_dict).analyze("ліс", "ліс")
        assert analysis.score == 1.0
        assert analysis.rhyme_part_a == analysis.rhyme_part_b

    def test_rhyming_pair_high_score(
        self, stress_dict: IStressDictionary,
    ) -> None:
        analysis = _make(stress_dict).analyze("ліс", "ріс")
        assert analysis.score >= 0.7

    def test_non_rhyming_pair_low_score(
        self, stress_dict: IStressDictionary,
    ) -> None:
        # «ліс» (1 syll, stressed `i`) and «вітер» (2 syll, stressed `i`,
        # then unstressed `er`) share only the stressed vowel — different
        # word lengths, different post-stress consonants. The score must
        # be well below the validator's 0.55 acceptance threshold; using
        # 0.7 (the docs' historical threshold) was lenient enough that a
        # broken implementation returning ~0.5 would still pass.
        analysis = _make(stress_dict).analyze("ліс", "вітер")
        assert analysis.score < 0.4

    def test_rhyme_part_starts_at_stressed_vowel(
        self, stress_dict: IStressDictionary,
    ) -> None:
        # Per the contract documented in rhyme_validation.md, the rhyme
        # part is the IPA suffix from the stressed vowel onward. For
        # «ліс» (single syllable, stressed `і` → IPA `i`) the rhyme part
        # must START with `i`. A type-only check would pass for any
        # string, including a broken implementation returning the full
        # word or an empty string.
        analysis = _make(stress_dict).analyze("ліс", "ріс")
        assert analysis.rhyme_part_a.startswith("i")
        assert analysis.rhyme_part_b.startswith("i")
        # Single-syllable rhymes can't be longer than the word itself.
        assert 1 <= len(analysis.rhyme_part_a) <= 3


class TestClausulaDetection:
    """Tests for clausula (line-ending stress) classification."""

    def test_masculine_clausula_monosyllable(
        self, stress_dict: IStressDictionary,
    ) -> None:
        """Monosyllabic word 'ліс' → masculine (stress on last syllable)."""
        analysis = _make(stress_dict).analyze("ліс", "ріс")
        assert analysis.clausula_a == ClausulaType.MASCULINE
        assert analysis.clausula_b == ClausulaType.MASCULINE

    def test_feminine_clausula(
        self, stress_dict: IStressDictionary,
    ) -> None:
        """'весна' has stress on last syllable → masculine.
        'літо' has stress on penultimate → feminine."""
        analysis = _make(stress_dict).analyze("літо", "діло")
        # Both words have 2 syllables with stress on the 1st → 1 trailing → feminine
        assert analysis.clausula_a == ClausulaType.FEMININE
        assert analysis.clausula_b == ClausulaType.FEMININE

    def test_dactylic_clausula(
        self, stress_dict: IStressDictionary,
    ) -> None:
        """'золото' — 3 syllables, stress on 1st → 2 trailing → dactylic."""
        analysis = _make(stress_dict).analyze("золото", "молоко")
        assert analysis.clausula_a == ClausulaType.DACTYLIC

    def test_unknown_for_empty_input(
        self, stress_dict: IStressDictionary,
    ) -> None:
        # The docstring of `_detect_clausula` promises UNKNOWN for empty /
        # syllable-less input. Keep the type-existence check here too —
        # but assert a *specific* value so a regression (e.g. silently
        # returning MASCULINE for empty) would fail.
        analysis = _make(stress_dict).analyze("", "")
        assert analysis.clausula_a == ClausulaType.UNKNOWN
        assert analysis.clausula_b == ClausulaType.UNKNOWN


class TestRhymePrecision:
    """Tests for rhyme precision classification."""

    def test_exact_rhyme(
        self, stress_dict: IStressDictionary,
    ) -> None:
        """Identical words should be classified as exact rhyme."""
        analysis = _make(stress_dict).analyze("ліс", "ліс")
        assert analysis.precision == RhymePrecision.EXACT

    def test_near_exact_rhyme(
        self, stress_dict: IStressDictionary,
    ) -> None:
        """Very similar rhyme parts like 'ліс'/'ріс' → exact."""
        analysis = _make(stress_dict).analyze("ліс", "ріс")
        assert analysis.precision == RhymePrecision.EXACT

    def test_pair_with_different_stressed_vowels_and_consonants_is_none(
        self, stress_dict: IStressDictionary,
    ) -> None:
        # «ліс» (stressed vowel `i`, post-stress `s`) vs «сон» (stressed
        # vowel `o`, post-stress `n`). Stressed vowels differ AND
        # post-stress consonants differ — the stressed-vowel gate must
        # reject the pair as NONE. A regression that classified this as
        # INEXACT (returning a small leaked similarity) would mean the
        # gate is bypassed.
        analysis = _make(stress_dict).analyze("ліс", "сон")
        assert analysis.precision == RhymePrecision.NONE
        assert analysis.score == 0.0


class TestStressedVowelGate:
    """Reject pairs that share only an unstressed grammatical suffix."""

    def test_shared_unstressed_suffix_drops_below_threshold(
        self, stress_dict: IStressDictionary,
    ) -> None:
        # «шибочках» / «кутиках»: post-stress sequences «-bɔtʃkax»
        # and «-kax» have very different lengths, so full-length
        # Levenshtein keeps similarity well below the 0.55 default
        # validator threshold. The pair must NOT pass as a rhyme.
        from src.config import ValidationConfig
        analysis = _make(stress_dict).analyze("шибочках", "кутиках")
        assert analysis.score < ValidationConfig().rhyme_threshold

    def test_matching_stressed_vowel_still_rhymes(
        self, stress_dict: IStressDictionary,
    ) -> None:
        # Stressed vowels coincide (-і-) → gate must not reject.
        analysis = _make(stress_dict).analyze("ліс", "ріс")
        assert analysis.score > 0.0
        assert analysis.precision != RhymePrecision.NONE

    def test_gate_rejects_when_stressed_vowel_and_consonants_differ(
        self, stress_dict: IStressDictionary,
    ) -> None:
        from src.infrastructure.text import LevenshteinSimilarity
        from src.infrastructure.validators.rhyme.pair_analyzer import (
            PhoneticRhymePairAnalyzer,
        )

        analyzer = PhoneticRhymePairAnalyzer(
            stress_resolver=None,  # type: ignore[arg-type]
            transcriber=None,  # type: ignore[arg-type]
            string_similarity=LevenshteinSimilarity(),
        )
        # «ebo» vs «olo»: stressed vowels e ≠ o; stressed-syllable
        # consonants «b» vs «l» do not match → gate rejects.
        assert analyzer._stressed_syllables_align("ebo", "olo") is False
        # «ebo» vs «obo»: stressed vowels e ≠ o but consonants «b» = «b»
        # (consonance pattern «по́лем / до́лом») → gate accepts.
        assert analyzer._stressed_syllables_align("ebo", "obo") is True
        # Equal stressed vowels → gate accepts unconditionally.
        assert analyzer._stressed_syllables_align("olo", "oro") is True
