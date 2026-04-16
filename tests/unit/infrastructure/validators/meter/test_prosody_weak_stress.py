"""Unit tests for weak stress word handling in actual_stress_pattern.

Verifies that monosyllabic function words ('і', 'до', 'як', 'бо') are
marked as unstressed in the actual stress pattern, while polysyllabic
weak words ('твої', 'вона') still receive stress.
"""
from __future__ import annotations

import pytest

from src.domain.ports import IStressDictionary
from src.infrastructure.meter import (
    DefaultSyllableFlagStrategy,
    UkrainianMeterTemplateProvider,
    UkrainianWeakStressLexicon,
)
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianSyllableCounter,
)
from src.infrastructure.validators.meter.prosody import UkrainianProsodyAnalyzer


class _DictStub(IStressDictionary):
    """Returns pre-configured stress indices for known words."""

    def __init__(self, overrides: dict[str, int] | None = None) -> None:
        self._overrides = overrides or {}

    def get_stress_index(self, word: str) -> int | None:
        return self._overrides.get(word.lower())


def _build(overrides: dict[str, int] | None = None) -> UkrainianProsodyAnalyzer:
    stub = _DictStub(overrides)
    resolver = PenultimateFallbackStressResolver(
        stress_dictionary=stub,
        syllable_counter=UkrainianSyllableCounter(),
    )
    lexicon = UkrainianWeakStressLexicon()
    return UkrainianProsodyAnalyzer(
        template_provider=UkrainianMeterTemplateProvider(),
        flag_strategy=DefaultSyllableFlagStrategy(weak_stress_lexicon=lexicon),
        stress_resolver=resolver,
        weak_stress_lexicon=lexicon,
    )


class TestMonosyllabicWeakWordsUnstressed:
    """Monosyllabic function words must be 'u' in the actual pattern."""

    @pytest.mark.parametrize("word", ["і", "й", "до", "як", "бо", "та", "в", "у", "з", "не"])
    def test_single_monosyllabic_weak_word_is_unstressed(self, word: str) -> None:
        analyzer = _build()
        pattern = analyzer.actual_stress_pattern([word], [1])
        assert pattern == ["u"], f"'{word}' should be unstressed but got {pattern}"

    def test_monosyllabic_weak_word_in_context(self) -> None:
        # "весна і літо" → весна(2 syl) + і(1 syl, weak) + літо(2 syl)
        analyzer = _build({"весна": 1, "літо": 0})
        pattern = analyzer.actual_stress_pattern(
            ["весна", "і", "літо"], [2, 1, 2],
        )
        # весна: [u, —], і: [u], літо: [—, u]
        assert pattern == ["u", "—", "u", "—", "u"]
        assert pattern[2] == "u"  # "і" is unstressed


class TestPolysyllabicWeakWordsStressed:
    """Polysyllabic weak words must still receive stress."""

    @pytest.mark.parametrize("word,syl", [("твої", 2), ("вона", 2), ("якщо", 2), ("тому", 2)])
    def test_polysyllabic_weak_word_gets_stress(self, word: str, syl: int) -> None:
        analyzer = _build()
        pattern = analyzer.actual_stress_pattern([word], [syl])
        assert "—" in pattern, f"'{word}' should receive stress but got {pattern}"


class TestContentWordsUnchanged:
    """Content words (not in weak set) always receive stress."""

    def test_monosyllabic_content_word_stressed(self) -> None:
        analyzer = _build()
        pattern = analyzer.actual_stress_pattern(["ліс"], [1])
        assert pattern == ["—"]

    def test_polysyllabic_content_word_stressed(self) -> None:
        analyzer = _build({"весна": 1})
        pattern = analyzer.actual_stress_pattern(["весна"], [2])
        assert pattern == ["u", "—"]
