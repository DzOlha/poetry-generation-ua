from __future__ import annotations

import pytest

from src.utils.distance import levenshtein_distance, normalized_similarity


class TestLevenshteinDistance:
    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("", "", 0),
            ("abc", "", 3),
            ("", "abc", 3),
            ("abc", "abc", 0),
            ("kitten", "sitting", 3),
            ("abc", "abd", 1),
        ],
    )
    def test_known_distances(self, a: str, b: str, expected: int):
        assert levenshtein_distance(a, b) == expected

    def test_symmetry(self):
        assert levenshtein_distance("hello", "world") == levenshtein_distance("world", "hello")


class TestNormalizedSimilarity:
    def test_identical_strings(self):
        assert normalized_similarity("abc", "abc") == 1.0

    def test_empty_strings(self):
        assert normalized_similarity("", "") == 1.0

    def test_completely_different(self):
        sim = normalized_similarity("aaa", "bbb")
        assert sim == 0.0

    def test_range_zero_to_one(self):
        sim = normalized_similarity("ліс", "ріс")
        assert 0.0 <= sim <= 1.0

    def test_similar_words_high_score(self):
        sim = normalized_similarity("ліс", "ріс")
        assert sim >= 0.5
