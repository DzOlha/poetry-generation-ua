"""Tests for the Ukrainian stress dictionary and the penultimate-fallback resolver."""
from __future__ import annotations

import pytest

from src.domain.ports import IStressDictionary
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianStressDict,
    UkrainianSyllableCounter,
)
from src.infrastructure.text import UkrainianTextProcessor

_TP = UkrainianTextProcessor()


def count_syllables_ua(word: str) -> int:
    return _TP.count_syllables(word)


class TestUkrainianStressDict:
    def test_instantiates_without_error(self, stress_dict: IStressDictionary):
        assert stress_dict is not None

    def test_get_stress_index_returns_int_or_none(self, stress_dict: IStressDictionary):
        result = stress_dict.get_stress_index("весна")
        assert result is None or isinstance(result, int)

    def test_get_stress_index_single_syllable(self, stress_dict: IStressDictionary):
        result = stress_dict.get_stress_index("ліс")
        assert result is None or result == 0

    def test_implements_interface(self, null_logger):
        sd = UkrainianStressDict(logger=null_logger)
        assert isinstance(sd, IStressDictionary)


class _NoOpStressDict(IStressDictionary):
    """Always returns None — useful for exercising the fallback heuristic."""

    def get_stress_index(self, word: str) -> int | None:
        return None


class TestPenultimateFallbackStressResolver:
    @pytest.fixture
    def fallback_resolver(self) -> PenultimateFallbackStressResolver:
        return PenultimateFallbackStressResolver(
            stress_dictionary=_NoOpStressDict(),
            syllable_counter=UkrainianSyllableCounter(),
        )

    def test_always_returns_int(self, stress_resolver):
        assert isinstance(stress_resolver.resolve("весна"), int)

    def test_vowel_final_gets_penultimate(self, fallback_resolver):
        # "стогне" ends in vowel → penultimate (index 0)
        assert fallback_resolver.resolve("стогне") == 0

    def test_consonant_final_gets_last(self, fallback_resolver):
        # "горить" ends in "ь" (soft final) → penultimate (index 0)
        # "вітер" ends in "р" (hard consonant) → last (index 1)
        assert fallback_resolver.resolve("вітер") == 1

    def test_soft_sign_final_gets_penultimate(self, fallback_resolver):
        # "місяць" ends in "ь" → penultimate (index 0)
        assert fallback_resolver.resolve("місяць") == 0

    def test_j_final_gets_penultimate(self, fallback_resolver):
        # "широкий" ends in "й" → penultimate (index 1)
        assert fallback_resolver.resolve("широкий") == 1

    def test_single_syllable_fallback(self, fallback_resolver):
        assert fallback_resolver.resolve("ліс") == 0

    @pytest.mark.parametrize("word", ["україна", "кохання", "перемога", "сонце", "вітер"])
    def test_result_within_syllable_range(self, stress_resolver, word: str):
        idx = stress_resolver.resolve(word)
        assert 0 <= idx < count_syllables_ua(word)
