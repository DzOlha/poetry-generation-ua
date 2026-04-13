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
        analysis = _make(stress_dict).analyze("ліс", "вітер")
        assert analysis.score < 0.7

    def test_rhyme_parts_are_strings(
        self, stress_dict: IStressDictionary,
    ) -> None:
        analysis = _make(stress_dict).analyze("день", "тінь")
        assert isinstance(analysis.rhyme_part_a, str)
        assert isinstance(analysis.rhyme_part_b, str)


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

    def test_clausula_fields_present(
        self, stress_dict: IStressDictionary,
    ) -> None:
        analysis = _make(stress_dict).analyze("день", "тінь")
        assert isinstance(analysis.clausula_a, ClausulaType)
        assert isinstance(analysis.clausula_b, ClausulaType)


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

    def test_non_rhyming_pair_none_or_inexact(
        self, stress_dict: IStressDictionary,
    ) -> None:
        """Completely different words should not be exact."""
        analysis = _make(stress_dict).analyze("ліс", "вітер")
        assert analysis.precision != RhymePrecision.EXACT

    def test_precision_field_present(
        self, stress_dict: IStressDictionary,
    ) -> None:
        analysis = _make(stress_dict).analyze("день", "тінь")
        assert isinstance(analysis.precision, RhymePrecision)
