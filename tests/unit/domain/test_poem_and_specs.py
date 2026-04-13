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
