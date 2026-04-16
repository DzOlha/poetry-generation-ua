"""Unit tests for the Ukrainian text processor — exercised via the public port.

The previous version of this module exercised bare free functions from
`src.shared.text_utils`. After the SOLID refactor that facade has been
deleted; consumers must depend on `ITextProcessor` (concretely
`UkrainianTextProcessor`) so these tests do the same.
"""
from __future__ import annotations

import pytest

from src.infrastructure.text import LevenshteinSimilarity, UkrainianTextProcessor
from src.shared.text_utils_ua import VOWELS_UA


@pytest.fixture
def tp() -> UkrainianTextProcessor:
    return UkrainianTextProcessor()


class TestVowelsConstant:
    def test_contains_all_ua_vowels(self):
        expected = set("аеєиіїоуюя")
        assert set(VOWELS_UA) == expected

    def test_no_consonants(self):
        for c in "бвгґджзклмнпрстфхцчшщь":
            assert c not in VOWELS_UA


class TestCountSyllables:
    @pytest.mark.parametrize(
        "word, expected",
        [
            ("весна", 2),
            ("ліс", 1),
            ("україна", 4),
            ("є", 1),
            ("ї", 1),
            ("сон", 1),
            ("", 0),
            ("бдж", 0),
        ],
    )
    def test_syllable_counts(self, tp: UkrainianTextProcessor, word: str, expected: int):
        assert tp.count_syllables(word) == expected


class TestExtractWords:
    def test_simple_sentence(self, tp: UkrainianTextProcessor):
        words = tp.extract_words("Весна прийшла у ліс")
        assert words == ["весна", "прийшла", "у", "ліс"]

    def test_with_punctuation(self, tp: UkrainianTextProcessor):
        words = tp.extract_words("Я тебе кохаю!")
        assert words == ["я", "тебе", "кохаю"]

    def test_apostrophe_preserved(self, tp: UkrainianTextProcessor):
        words = tp.extract_words("пам'ятник м'який")
        assert len(words) == 2

    def test_unicode_right_quote_apostrophe(self, tp: UkrainianTextProcessor):
        # U+2019 (right single quotation mark) — common in web input
        words = tp.extract_words("нап\u2019ються")
        assert len(words) == 1
        assert words[0] == "нап\u2019ються"

    def test_modifier_letter_apostrophe(self, tp: UkrainianTextProcessor):
        # U+02BC (modifier letter apostrophe) — Ukrainian standard
        words = tp.extract_words("пам\u02BCятник")
        assert len(words) == 1

    def test_empty_string(self, tp: UkrainianTextProcessor):
        assert tp.extract_words("") == []

    def test_digits_excluded(self, tp: UkrainianTextProcessor):
        words = tp.extract_words("рік 2024 весна")
        assert words == ["рік", "весна"]


class TestNormalizeWhitespace:
    def test_multiple_spaces(self, tp: UkrainianTextProcessor):
        assert tp.normalize_whitespace("  hello   world  ") == "hello world"

    def test_tabs_newlines(self, tp: UkrainianTextProcessor):
        assert tp.normalize_whitespace("a\t\nb") == "a b"


class TestSplitLines:
    def test_basic(self, tp: UkrainianTextProcessor):
        text = "рядок один\n\nрядок два\n   \nрядок три\n"
        assert tp.split_lines(text) == ["рядок один", "рядок два", "рядок три"]

    def test_empty_string(self, tp: UkrainianTextProcessor):
        assert tp.split_lines("") == []


class TestTokenizeLine:
    def test_basic_tokenization(self, tp: UkrainianTextProcessor):
        tokens = tp.tokenize_line("Весна прийшла у ліс")
        assert tokens.words == ("весна", "прийшла", "у", "ліс")
        assert tokens.syllables_per_word == (2, 2, 1, 1)

    def test_empty_line(self, tp: UkrainianTextProcessor):
        tokens = tp.tokenize_line("")
        assert tokens.words == ()
        assert tokens.syllables_per_word == ()


class TestStringSimilarity:
    def test_identical(self):
        sim = LevenshteinSimilarity()
        assert sim.similarity("abc", "abc") == 1.0

    def test_range(self):
        sim = LevenshteinSimilarity()
        assert 0.0 <= sim.similarity("ліс", "ріс") <= 1.0
