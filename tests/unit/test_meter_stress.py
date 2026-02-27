from __future__ import annotations

import pytest

from src.meter.stress import StressDict, get_stress_index_safe
from src.utils.text import count_syllables_ua


class TestStressDict:
    def test_instantiates_without_error(self, stress_dict: StressDict):
        assert stress_dict is not None

    def test_get_stress_index_returns_int_or_none(self, stress_dict: StressDict):
        result = stress_dict.get_stress_index("весна")
        assert result is None or isinstance(result, int)

    def test_get_stress_index_single_syllable(self, stress_dict: StressDict):
        result = stress_dict.get_stress_index("ліс")
        assert result is None or result == 0


class TestGetStressIndexSafe:
    def test_always_returns_int(self, stress_dict: StressDict):
        result = get_stress_index_safe("весна", stress_dict)
        assert isinstance(result, int)

    def test_fallback_last_syllable(self):
        dummy = StressDict.__new__(StressDict)
        dummy._stressify = None
        dummy._accent = "\u0301"
        dummy.on_ambiguity = "first"

        idx = get_stress_index_safe("весна", dummy)
        assert idx == count_syllables_ua("весна") - 1

    def test_single_syllable_fallback(self):
        dummy = StressDict.__new__(StressDict)
        dummy._stressify = None
        dummy._accent = "\u0301"
        dummy.on_ambiguity = "first"

        idx = get_stress_index_safe("ліс", dummy)
        assert idx == 0

    @pytest.mark.parametrize("word", ["україна", "кохання", "перемога", "сонце", "вітер"])
    def test_result_within_syllable_range(self, stress_dict: StressDict, word: str):
        idx = get_stress_index_safe(word, stress_dict)
        syllables = count_syllables_ua(word)
        assert 0 <= idx < syllables
