from __future__ import annotations

import pytest

from src.utils.text import (
    VOWELS_UA,
    count_syllables_ua,
    extract_words_ua,
    normalize_whitespace,
    split_nonempty_lines,
    tokenize_line_ua,
)


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
    def test_syllable_counts(self, word: str, expected: int):
        assert count_syllables_ua(word) == expected


class TestExtractWords:
    def test_simple_sentence(self):
        words = extract_words_ua("Весна прийшла у ліс")
        assert words == ["весна", "прийшла", "у", "ліс"]

    def test_with_punctuation(self):
        words = extract_words_ua("Я тебе кохаю!")
        assert words == ["я", "тебе", "кохаю"]

    def test_apostrophe_preserved(self):
        words = extract_words_ua("пам'ятник м'який")
        assert len(words) == 2

    def test_empty_string(self):
        assert extract_words_ua("") == []

    def test_digits_excluded(self):
        words = extract_words_ua("рік 2024 весна")
        assert words == ["рік", "весна"]


class TestNormalizeWhitespace:
    def test_multiple_spaces(self):
        assert normalize_whitespace("  hello   world  ") == "hello world"

    def test_tabs_newlines(self):
        assert normalize_whitespace("a\t\nb") == "a b"


class TestSplitNonemptyLines:
    def test_basic(self):
        text = "рядок один\n\nрядок два\n   \nрядок три\n"
        lines = split_nonempty_lines(text)
        assert lines == ["рядок один", "рядок два", "рядок три"]

    def test_empty_string(self):
        assert split_nonempty_lines("") == []


class TestTokenizeLineUa:
    def test_basic_tokenization(self):
        tokens = tokenize_line_ua("Весна прийшла у ліс")
        assert tokens.words == ["весна", "прийшла", "у", "ліс"]
        assert tokens.syllables_per_word == [2, 2, 1, 1]

    def test_empty_line(self):
        tokens = tokenize_line_ua("")
        assert tokens.words == []
        assert tokens.syllables_per_word == []
