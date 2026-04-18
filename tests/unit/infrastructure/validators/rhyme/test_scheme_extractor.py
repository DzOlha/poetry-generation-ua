"""Unit tests for StandardRhymeSchemeExtractor — multi-stanza pair extraction."""
from __future__ import annotations

import pytest

from src.domain.errors import UnsupportedConfigError
from src.infrastructure.validators.rhyme.scheme_extractor import StandardRhymeSchemeExtractor


@pytest.fixture
def extractor() -> StandardRhymeSchemeExtractor:
    return StandardRhymeSchemeExtractor()


class TestSingleStanza:
    def test_abab_4_lines(self, extractor: StandardRhymeSchemeExtractor) -> None:
        assert extractor.extract_pairs("ABAB", 4) == [(0, 2), (1, 3)]

    def test_aabb_4_lines(self, extractor: StandardRhymeSchemeExtractor) -> None:
        assert extractor.extract_pairs("AABB", 4) == [(0, 1), (2, 3)]

    def test_abba_4_lines(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("ABBA", 4)
        assert (0, 3) in pairs
        assert (1, 2) in pairs

    def test_too_few_lines_returns_empty(self, extractor: StandardRhymeSchemeExtractor) -> None:
        assert extractor.extract_pairs("ABAB", 3) == []

    def test_empty_scheme_returns_empty(self, extractor: StandardRhymeSchemeExtractor) -> None:
        assert extractor.extract_pairs("", 4) == []


class TestMultiStanza:
    def test_abab_8_lines_two_stanzas(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("ABAB", 8)
        assert pairs == [(0, 2), (1, 3), (4, 6), (5, 7)]

    def test_aabb_8_lines_two_stanzas(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("AABB", 8)
        assert pairs == [(0, 1), (2, 3), (4, 5), (6, 7)]

    def test_abba_12_lines_three_stanzas(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("ABBA", 12)
        assert len(pairs) == 6
        # Stanza 1
        assert (0, 3) in pairs
        assert (1, 2) in pairs
        # Stanza 3
        assert (8, 11) in pairs
        assert (9, 10) in pairs

    def test_incomplete_last_stanza_ignored(self, extractor: StandardRhymeSchemeExtractor) -> None:
        # 6 lines with ABAB: only first stanza (lines 0-3), lines 4-5 incomplete
        pairs = extractor.extract_pairs("ABAB", 6)
        assert pairs == [(0, 2), (1, 3)]

    def test_exact_multiple_of_stanza_size(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("ABAB", 12)
        assert len(pairs) == 6  # 3 stanzas × 2 pairs each


class TestEdgeCases:
    def test_case_insensitive(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("abab", 4)
        assert pairs == [(0, 2), (1, 3)]

    def test_whitespace_stripped(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("  ABAB  ", 4)
        assert pairs == [(0, 2), (1, 3)]

    def test_no_repeated_letters_raises(self, extractor: StandardRhymeSchemeExtractor) -> None:
        with pytest.raises(UnsupportedConfigError, match="Невідома схема римування"):
            extractor.extract_pairs("ABCD", 4)

    def test_aaaa_all_pairs_single_stanza(self, extractor: StandardRhymeSchemeExtractor) -> None:
        pairs = extractor.extract_pairs("AAAA", 4)
        assert (0, 1) in pairs
        assert (0, 2) in pairs
        assert (0, 3) in pairs
        assert (1, 2) in pairs
        assert (1, 3) in pairs
        assert (2, 3) in pairs
