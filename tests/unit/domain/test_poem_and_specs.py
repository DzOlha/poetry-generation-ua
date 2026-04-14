"""Tests for the domain behaviour added during the SOLID refactor.

Covers:
  - The new `Poem` aggregate (replaces ad-hoc `split_nonempty_lines` calls).
  - `MeterSpec` strict parsing (fail-fast on unknown meters).

Note: pair-indices logic is tested via `StandardRhymeSchemeExtractor` in
``tests/unit/infrastructure/validators/rhyme/``.
"""
from __future__ import annotations

import pytest

from src.domain.errors import UnsupportedConfigError
from src.domain.models import MeterSpec, Poem, RhymeScheme


class TestPoem:
    def test_from_text_trims_and_drops_blank_lines(self):
        poem = Poem.from_text("  рядок один  \n\nрядок два\n   \nрядок три\n")
        assert poem.lines == ("рядок один", "рядок два", "рядок три")
        assert poem.line_count == 3
        assert not poem.is_empty

    def test_empty_text_produces_empty_poem(self):
        poem = Poem.from_text("")
        assert poem.is_empty
        assert poem.line_count == 0
        assert poem.as_text() == ""

    def test_as_text_roundtrips(self):
        poem = Poem.from_text("рядок один\nрядок два\n")
        assert poem.as_text() == "рядок один\nрядок два\n"

    def test_drops_allcaps_cyrillic_scansion_line(self):
        poem = Poem.from_text(
            "Від давніх тих часів,\n"
            "І-ДУТЬ у СЛАВ-ний БІЙ те-ПЕР но-ВІ пол-КИ.\n"
            "крізь біль гірких віків\n"
        )
        assert poem.lines == (
            "Від давніх тих часів,",
            "крізь біль гірких віків",
        )

    def test_drops_paren_digit_syllable_numbering(self):
        poem = Poem.from_text(
            "звичайний рядок один\n"
            "Слу(1) жи(2) ли(3) всі(4) лі(5) си(6) і(7) рі(8) ки(9).\n"
            "А (1) ни (2) ні (3) т\n"
            "звичайний рядок два\n"
        )
        assert poem.lines == (
            "звичайний рядок один",
            "звичайний рядок два",
        )

    def test_drops_digit_only_line(self):
        poem = Poem.from_text(
            "рядок перший\n"
            "1 2 3 4 5 6 7 8\n"
            "рядок другий\n"
        )
        assert poem.lines == ("рядок перший", "рядок другий")

    def test_drops_caps_hyphen_syllable_cyrillic(self):
        # Cyrillic uppercase syllable with hyphens like "РІД-ну ЗЕМ-лю"
        poem = Poem.from_text(
            "нормальний перший рядок\n"
            "І РІД-ну ЗЕМ-лю роз-пи-НА-ли\n"
            "нормальний третій рядок\n"
        )
        assert poem.lines == (
            "нормальний перший рядок",
            "нормальний третій рядок",
        )

    def test_keeps_single_capital_word_line(self):
        # A single leading capitalized word (proper noun) is fine.
        poem = Poem.from_text("Україна — моя земля.\n")
        assert poem.lines == ("Україна — моя земля.",)

    def test_keeps_single_allcaps_token(self):
        # One ALL-CAPS token is tolerated (e.g. acronym); scansion lines have ≥2.
        poem = Poem.from_text("Настав час УНР здобути волю.\n")
        assert poem.lines == ("Настав час УНР здобути волю.",)


class TestRhymeScheme:
    def test_parses_known_patterns(self):
        assert RhymeScheme("ABAB").pattern == "ABAB"
        assert RhymeScheme("AABB").pattern == "AABB"
        assert RhymeScheme("ABBA").pattern == "ABBA"
        assert RhymeScheme("AAAA").pattern == "AAAA"

    def test_as_enum_accessor(self):
        from src.domain.values import RhymePattern

        assert RhymeScheme("ABAB").as_enum == RhymePattern.ABAB

    def test_unknown_pattern_raises(self):
        with pytest.raises(UnsupportedConfigError):
            RhymeScheme("XYZW")


class TestMeterSpecStrictness:
    def test_known_meter_canonicalises(self):
        assert MeterSpec(name="iamb", foot_count=4).name == "ямб"

    def test_unknown_meter_fails_fast(self):
        with pytest.raises(UnsupportedConfigError):
            MeterSpec(name="гекзаметр", foot_count=4)

    def test_negative_foot_count_rejected(self):
        with pytest.raises(UnsupportedConfigError):
            MeterSpec(name="ямб", foot_count=-1)
