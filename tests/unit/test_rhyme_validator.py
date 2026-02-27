from __future__ import annotations

import pytest

from src.meter.stress import StressDict
from src.rhyme.validator import (
    RhymeCheckResult,
    RhymePairResult,
    check_rhyme,
    rhyme_feedback,
    rhyme_score,
)


class TestRhymeScore:
    def test_identical_words_high_score(self, stress_dict: StressDict):
        _, _, score = rhyme_score("ліс", "ліс", stress_dict)
        assert score == 1.0

    def test_rhyming_pair_high_score(self, stress_dict: StressDict):
        _, _, score = rhyme_score("ліс", "ріс", stress_dict)
        assert score >= 0.7

    def test_non_rhyming_pair_low_score(self, stress_dict: StressDict):
        _, _, score = rhyme_score("ліс", "вітер", stress_dict)
        assert score < 0.7

    def test_returns_rhyme_parts(self, stress_dict: StressDict):
        r1, r2, score = rhyme_score("день", "тінь", stress_dict)
        assert isinstance(r1, str)
        assert isinstance(r2, str)
        assert isinstance(score, float)


class TestCheckRhyme:
    def test_abab_scheme(self, stress_dict: StressDict):
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "І спів пташок в гіллі бринить.\n"
            "Струмок біжить, мов шлях натхнений,\n"
            "І сонце крізь туман горить.\n"
        )
        result = check_rhyme(poem, "ABAB", stress_dict)
        assert isinstance(result, RhymeCheckResult)
        assert isinstance(result.is_valid, bool)
        assert len(result.pairs) == 2

    def test_aabb_scheme_pair_count(self, stress_dict: StressDict):
        poem = "рядок один\nрядок два\nрядок три\nрядок чотири\n"
        result = check_rhyme(poem, "AABB", stress_dict)
        assert len(result.pairs) == 2

    def test_abba_scheme_pair_count(self, stress_dict: StressDict):
        poem = "рядок один\nрядок два\nрядок три\nрядок чотири\n"
        result = check_rhyme(poem, "ABBA", stress_dict)
        assert len(result.pairs) == 2

    def test_aaaa_scheme(self, stress_dict: StressDict):
        poem = "ліс\nріс\nвіс\nніс\n"
        result = check_rhyme(poem, "AAAA", stress_dict)
        assert len(result.pairs) == 6  # C(4,2)

    def test_unsupported_scheme_raises(self, stress_dict: StressDict):
        with pytest.raises(ValueError, match="Unsupported rhyme scheme"):
            check_rhyme("a\nb\nc\nd\n", "XYZW", stress_dict)

    def test_too_few_lines_returns_empty_pairs(self, stress_dict: StressDict):
        result = check_rhyme("один рядок\n", "ABAB", stress_dict)
        assert result.pairs == []
        assert result.is_valid is True


class TestRhymeFeedback:
    def test_feedback_format(self):
        pair = RhymePairResult(
            line_1=3,
            line_2=4,
            word_1="ліс",
            word_2="вітер",
            rhyme_part_1="is",
            rhyme_part_2="iter",
            score=0.21,
            rhyme_ok=False,
        )
        fb = rhyme_feedback(pair, "AABB")
        assert "Lines 3 and 4" in fb
        assert "AABB" in fb
        assert "0.21" in fb
        assert "Rewrite line 4" in fb
