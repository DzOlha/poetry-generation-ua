from __future__ import annotations

import pytest

from src.domain.errors import UnsupportedConfigError
from src.domain.models import RhymeResult, RhymeScheme
from src.domain.ports import IStressDictionary
from src.infrastructure.feedback import UkrainianFeedbackFormatter
from src.infrastructure.phonetics import UkrainianIpaTranscriber
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianSyllableCounter,
)
from src.infrastructure.text import LevenshteinSimilarity, UkrainianTextProcessor
from src.infrastructure.validators.rhyme.pair_analyzer import PhoneticRhymePairAnalyzer
from src.infrastructure.validators.rhyme.phonetic_validator import PhoneticRhymeValidator
from src.infrastructure.validators.rhyme.scheme_extractor import StandardRhymeSchemeExtractor


def _make_pair_analyzer(stress_dict: IStressDictionary) -> PhoneticRhymePairAnalyzer:
    syllable_counter = UkrainianSyllableCounter()
    resolver = PenultimateFallbackStressResolver(
        stress_dictionary=stress_dict,
        syllable_counter=syllable_counter,
    )
    return PhoneticRhymePairAnalyzer(
        stress_resolver=resolver,
        transcriber=UkrainianIpaTranscriber(),
        string_similarity=LevenshteinSimilarity(),
        syllable_counter=syllable_counter,
    )


def _make_validator(stress_dict: IStressDictionary) -> PhoneticRhymeValidator:
    tp = UkrainianTextProcessor()
    return PhoneticRhymeValidator(
        line_splitter=tp,
        tokenizer=tp,
        scheme_extractor=StandardRhymeSchemeExtractor(),
        pair_analyzer=_make_pair_analyzer(stress_dict),
    )


class TestRhymeScore:
    def test_identical_words_high_score(self, stress_dict: IStressDictionary):
        analysis = _make_pair_analyzer(stress_dict).analyze("ліс", "ліс")
        assert analysis.score == 1.0

    def test_rhyming_pair_high_score(self, stress_dict: IStressDictionary):
        analysis = _make_pair_analyzer(stress_dict).analyze("ліс", "ріс")
        assert analysis.score >= 0.7

    def test_non_rhyming_pair_low_score(self, stress_dict: IStressDictionary):
        analysis = _make_pair_analyzer(stress_dict).analyze("ліс", "вітер")
        assert analysis.score < 0.7

    def test_returns_rhyme_parts(self, stress_dict: IStressDictionary):
        analysis = _make_pair_analyzer(stress_dict).analyze("день", "тінь")
        assert isinstance(analysis.rhyme_part_a, str)
        assert isinstance(analysis.rhyme_part_b, str)
        assert isinstance(analysis.score, float)


class TestCheckRhyme:
    def test_abab_scheme(self, stress_dict: IStressDictionary):
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "І спів пташок в гіллі бринить.\n"
            "Струмок біжить, мов шлях натхнений,\n"
            "І сонце крізь туман горить.\n"
        )
        result = _make_validator(stress_dict).validate(poem, RhymeScheme("ABAB"))
        assert isinstance(result, RhymeResult)
        assert len(result.pair_results) == 2

    def test_aabb_scheme_pair_count(self, stress_dict: IStressDictionary):
        result = _make_validator(stress_dict).validate(
            "рядок один\nрядок два\nрядок три\nрядок чотири\n",
            RhymeScheme("AABB"),
        )
        assert len(result.pair_results) == 2

    def test_abba_scheme_pair_count(self, stress_dict: IStressDictionary):
        result = _make_validator(stress_dict).validate(
            "рядок один\nрядок два\nрядок три\nрядок чотири\n",
            RhymeScheme("ABBA"),
        )
        assert len(result.pair_results) == 2

    def test_aaaa_scheme(self, stress_dict: IStressDictionary):
        result = _make_validator(stress_dict).validate(
            "ліс\nріс\nвіс\nніс\n", RhymeScheme("AAAA"),
        )
        assert len(result.pair_results) == 6  # C(4,2)

    def test_unsupported_scheme_raises(self, stress_dict: IStressDictionary):
        scheme = object.__new__(RhymeScheme)
        object.__setattr__(scheme, "pattern", "XYZW")
        with pytest.raises(UnsupportedConfigError, match="Невідома схема римування"):
            _make_validator(stress_dict).validate("a\nb\nc\nd\n", scheme)

    def test_too_few_lines_returns_empty_pairs(self, stress_dict: IStressDictionary):
        result = _make_validator(stress_dict).validate("один рядок\n", RhymeScheme("ABAB"))
        assert result.pair_results == ()
        assert result.ok is True


class TestRhymeFeedback:
    def test_feedback_format(self, stress_dict: IStressDictionary):
        from src.domain.models.feedback import PairFeedback

        pair = PairFeedback(
            line_a_idx=2,
            line_b_idx=3,
            scheme_pattern="AABB",
            word_a="ліс",
            word_b="вітер",
            rhyme_part_a="is",
            rhyme_part_b="iter",
            score=0.21,
        )
        fb = UkrainianFeedbackFormatter().format_pair(pair)
        assert "Lines 3 and 4" in fb
        assert "AABB" in fb
        assert "0.21" in fb
        assert "Rewrite line 4" in fb
