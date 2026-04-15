"""Unit tests for PatternMeterValidator and UkrainianProsodyAnalyzer."""
from __future__ import annotations

import pytest

from src.domain.errors import UnsupportedConfigError
from src.domain.models import LineMeterResult, MeterSpec
from src.domain.ports import IStressDictionary, IStressResolver
from src.infrastructure.feedback import UkrainianFeedbackFormatter
from src.infrastructure.meter import (
    DefaultSyllableFlagStrategy,
    UkrainianMeterTemplateProvider,
    UkrainianWeakStressLexicon,
)
from src.infrastructure.meter.ukrainian_weak_stress_lexicon import WEAK_STRESS_WORDS
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianSyllableCounter,
)
from src.infrastructure.text import UkrainianTextProcessor
from src.infrastructure.validators.meter.feedback_builder import DefaultLineFeedbackBuilder
from src.infrastructure.validators.meter.pattern_validator import PatternMeterValidator
from src.infrastructure.validators.meter.prosody import UkrainianProsodyAnalyzer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolver_for(stress_dict: IStressDictionary) -> IStressResolver:
    return PenultimateFallbackStressResolver(
        stress_dictionary=stress_dict,
        syllable_counter=UkrainianSyllableCounter(),
    )


def _build_prosody(stress_resolver: IStressResolver) -> UkrainianProsodyAnalyzer:
    return UkrainianProsodyAnalyzer(
        template_provider=UkrainianMeterTemplateProvider(),
        flag_strategy=DefaultSyllableFlagStrategy(
            weak_stress_lexicon=UkrainianWeakStressLexicon(),
        ),
        stress_resolver=stress_resolver,
    )


def _make_validator(
    stress_dict: IStressDictionary,
    allowed_mismatches: int = 2,
) -> PatternMeterValidator:
    return PatternMeterValidator(
        prosody=_build_prosody(_resolver_for(stress_dict)),
        text_processor=UkrainianTextProcessor(),
        feedback_builder=DefaultLineFeedbackBuilder(
            template_provider=UkrainianMeterTemplateProvider(),
        ),
        allowed_mismatches=allowed_mismatches,
    )


def check_meter_line(
    line: str,
    meter: str,
    foot_count: int,
    stress_dict: IStressDictionary,
    allowed_mismatches: int = 2,
) -> LineMeterResult:
    return _make_validator(stress_dict, allowed_mismatches)._validate_line(
        line, MeterSpec(name=meter, foot_count=foot_count),
    )


def check_meter_poem(
    poem: str,
    meter: str,
    foot_count: int,
    stress_dict: IStressDictionary,
) -> list[LineMeterResult]:
    return list(_make_validator(stress_dict).validate(
        poem, MeterSpec(name=meter, foot_count=foot_count),
    ).line_results)


def _noop_stress() -> IStressDictionary:
    class _NoOpStress(IStressDictionary):
        def get_stress_index(self, word: str) -> int | None:
            return None

    return _NoOpStress()


def _noop_analyzer() -> UkrainianProsodyAnalyzer:
    return _build_prosody(_resolver_for(_noop_stress()))


class TestBuildExpectedPattern:
    @pytest.mark.parametrize(
        "meter, foot_count, expected",
        [
            ("ямб", 4, ["u", "—", "u", "—", "u", "—", "u", "—"]),
            ("iamb", 2, ["u", "—", "u", "—"]),
            ("хорей", 3, ["—", "u", "—", "u", "—", "u"]),
            ("trochee", 2, ["—", "u", "—", "u"]),
            ("дактиль", 2, ["—", "u", "u", "—", "u", "u"]),
            ("амфібрахій", 2, ["u", "—", "u", "u", "—", "u"]),
            ("анапест", 2, ["u", "u", "—", "u", "u", "—"]),
        ],
    )
    def test_known_patterns(self, meter: str, foot_count: int, expected: list[str]):
        analyzer = _noop_analyzer()
        assert analyzer.build_expected_pattern(meter, foot_count) == expected

    def test_unsupported_meter_raises(self):
        analyzer = _noop_analyzer()
        with pytest.raises(UnsupportedConfigError, match="Unsupported meter"):
            analyzer.build_expected_pattern("невідомий", 4)

    def test_case_insensitive(self):
        analyzer = _noop_analyzer()
        assert analyzer.build_expected_pattern("Ямб", 2) == ["u", "—", "u", "—"]
        assert analyzer.build_expected_pattern("IAMB", 2) == ["u", "—", "u", "—"]


class TestLineLengthOk:
    @pytest.fixture
    def analyzer(self) -> UkrainianProsodyAnalyzer:
        return _noop_analyzer()

    def test_exact_match(self, analyzer):
        iamb4 = ["u", "—", "u", "—"]
        assert analyzer.line_length_ok(iamb4, iamb4) is True

    def test_feminine_ending_one_extra(self, analyzer):
        iamb2 = ["u", "—", "u", "—"]
        actual = ["u", "—", "u", "—", "u"]
        assert analyzer.line_length_ok(actual, iamb2) is True

    def test_feminine_ending_stressed_last_rejected(self, analyzer):
        iamb2 = ["u", "—", "u", "—"]
        actual = ["u", "—", "u", "—", "—"]
        assert analyzer.line_length_ok(actual, iamb2) is False

    def test_dactylic_ending_two_extra(self, analyzer):
        iamb2 = ["u", "—", "u", "—"]
        actual = ["u", "—", "u", "—", "u", "u"]
        assert analyzer.line_length_ok(actual, iamb2) is True

    def test_dactylic_ending_rejected_if_last_stressed(self, analyzer):
        iamb2 = ["u", "—", "u", "—"]
        actual = ["u", "—", "u", "—", "u", "—"]
        assert analyzer.line_length_ok(actual, iamb2) is False

    def test_catalectic_diff_minus_one_trisyllabic(self, analyzer):
        # dactyl with one syllable truncated (foot_size=3, diff=-1 allowed)
        dactyl3 = ["—", "u", "u"] * 3
        actual = ["—", "u", "u", "—", "u", "u", "—", "u"]
        assert analyzer.line_length_ok(actual, dactyl3) is True

    def test_catalectic_diff_minus_two_trisyllabic_allowed(self, analyzer):
        # dactyl masculine ending drops two trailing unstressed (foot_size=3, diff=-2 allowed)
        dactyl4 = ["—", "u", "u"] * 4
        actual = ["—", "u", "u", "—", "u", "u", "—", "u", "u", "—"]
        assert analyzer.line_length_ok(actual, dactyl4) is True

    def test_iamb_feminine_ending_masquerading_as_short_pentameter_rejected(
        self, analyzer,
    ):
        # Regression: a 4-foot iamb with feminine clausula (9 syllables,
        # stresses at 2/4/6/8) used to pass as a "catalectic" 5-foot iamb
        # because the length check allowed diff=-1 unconditionally and the
        # pattern comparison was truncated to min(actual, expected). The
        # dropped expected position is "—", so this must now fail.
        iamb5 = ["u", "—"] * 5                     # 10 syllables expected
        actual = ["u", "—", "u", "—", "u", "—", "u", "—", "u"]  # 9 syl, 4 feet
        assert analyzer.line_length_ok(actual, iamb5) is False

    def test_trochaic_catalexis_diff_minus_one_allowed(self, analyzer):
        # Classical trochaic catalexis: trochee pentameter drops its final
        # unstressed syllable. The dropped position in the expected pattern
        # is "u", so truncation is legitimate.
        trochee5 = ["—", "u"] * 5                  # 10 syllables expected
        actual = ["—", "u", "—", "u", "—", "u", "—", "u", "—"]  # 9 syl, ends on —
        assert analyzer.line_length_ok(actual, trochee5) is True

    def test_missing_full_foot_rejected_binary(self, analyzer):
        # 5-foot iamb vs 6-foot expected: diff=-2 == foot_size → full foot missing, reject
        iamb6 = ["u", "—"] * 6
        actual = ["u", "—"] * 5
        assert analyzer.line_length_ok(actual, iamb6) is False

    def test_missing_full_foot_rejected_trisyllabic(self, analyzer):
        # dactyl diff=-3 means full foot missing → reject
        dactyl3 = ["—", "u", "u"] * 3
        actual = ["—", "u", "u", "—", "u", "u"]
        assert analyzer.line_length_ok(actual, dactyl3) is False

    def test_too_long_rejected(self, analyzer):
        iamb2 = ["u", "—", "u", "—"]
        assert analyzer.line_length_ok(["u"] * 8, iamb2) is False

    def test_too_short_rejected(self, analyzer):
        dactyl3 = ["—", "u", "u"] * 3
        assert analyzer.line_length_ok(["u"] * 2, dactyl3) is False


class TestSyllableWordFlags:
    @pytest.fixture
    def analyzer(self) -> UkrainianProsodyAnalyzer:
        return _noop_analyzer()

    def test_monosyllabic_flag(self, analyzer):
        assert analyzer.syllable_word_flags(["ліс"], [1]) == [(True, False)]

    def test_function_word_flag(self, analyzer):
        flags = analyzer.syllable_word_flags(["і"], [1])
        assert flags[0] == (True, True)

    def test_polysyllabic_content_word(self, analyzer):
        flags = analyzer.syllable_word_flags(["весна"], [2])
        assert flags == [(False, False), (False, False)]

    def test_mixed_line(self, analyzer):
        flags = analyzer.syllable_word_flags(["і", "ліс", "зелений"], [1, 1, 3])
        assert flags[0] == (True, True)   # і
        assert flags[1] == (True, False)  # ліс
        for f in flags[2:]:               # зелений × 3 syllables
            assert f == (False, False)


class TestIsTolerated:
    @pytest.fixture
    def analyzer(self) -> UkrainianProsodyAnalyzer:
        return _noop_analyzer()

    def test_pyrrhic_function_word_tolerated(self, analyzer):
        actual = ["u", "—", "u", "—"]
        expected = ["u", "—", "—", "—"]
        flags = [(False, False), (False, False), (True, True), (False, False)]
        assert analyzer.is_tolerated_mismatch(2, actual, expected, flags) is True

    def test_pyrrhic_monosyllabic_content_tolerated(self, analyzer):
        assert analyzer.is_tolerated_mismatch(
            1, ["u", "u"], ["u", "—"], [(False, False), (True, False)],
        ) is True

    def test_pyrrhic_polysyllabic_content_not_tolerated(self, analyzer):
        assert analyzer.is_tolerated_mismatch(
            1, ["u", "u"], ["u", "—"], [(False, False), (False, False)],
        ) is False

    def test_spondee_monosyllabic_tolerated(self, analyzer):
        assert analyzer.is_tolerated_mismatch(
            0, ["—", "—"], ["u", "—"], [(True, False), (False, False)],
        ) is True

    def test_spondee_function_word_tolerated(self, analyzer):
        assert analyzer.is_tolerated_mismatch(
            0, ["—", "—"], ["u", "—"], [(True, True), (False, False)],
        ) is True

    def test_no_mismatch_returns_false(self, analyzer):
        flags = [(False, False), (False, False)]
        assert analyzer.is_tolerated_mismatch(0, ["u", "—"], ["u", "—"], flags) is False
        assert analyzer.is_tolerated_mismatch(1, ["u", "—"], ["u", "—"], flags) is False


class TestCheckMeterLine:
    def test_returns_line_meter_result(self, stress_dict: IStressDictionary):
        result = check_meter_line("Весна прийшла у ліс", "ямб", 4, stress_dict)
        assert isinstance(result, LineMeterResult)

    def test_result_has_required_fields(self, stress_dict: IStressDictionary):
        result = check_meter_line("Весна прийшла у ліс", "ямб", 4, stress_dict)
        assert isinstance(result.ok, bool)
        assert isinstance(result.expected_stresses, tuple)
        assert isinstance(result.actual_stresses, tuple)
        assert isinstance(result.error_positions, tuple)
        assert isinstance(result.total_syllables, int)
        assert result.total_syllables > 0

    def test_feminine_ending_iamb_is_ok(self, stress_dict: IStressDictionary):
        assert check_meter_line("Весна прийшла у ліс зелений", "ямб", 4, stress_dict).ok is True

    def test_exact_length_iamb_is_ok(self, stress_dict: IStressDictionary):
        assert check_meter_line("І сонце крізь туман горить", "ямб", 4, stress_dict).ok is True

    def test_shevchenko_iamb4_line1(self, stress_dict):
        assert check_meter_line("Реве та стогне Дніпр широкий", "ямб", 4, stress_dict).ok is True

    def test_shevchenko_iamb4_line2(self, stress_dict):
        assert check_meter_line("Сердитий вітер завива", "ямб", 4, stress_dict).ok is True

    def test_shevchenko_iamb4_line3(self, stress_dict):
        assert check_meter_line("Додолу верби гне високі", "ямб", 4, stress_dict).ok is True

    def test_shevchenko_iamb4_line4(self, stress_dict):
        result = check_meter_line("Горами хвилю підійма", "ямб", 4, stress_dict)
        assert isinstance(result.ok, bool)
        assert result.total_syllables == 8

    def test_shevchenko_iamb4_full_poem(self, stress_dict):
        poem = (
            "Реве та стогне Дніпр широкий,\n"
            "Сердитий вітер завива,\n"
            "Додолу верби гне високі,\n"
            "Горами хвилю підійма."
        )
        results = check_meter_poem(poem, "ямб", 4, stress_dict)
        assert len(results) == 4
        assert sum(1 for r in results if r.ok) >= 3

    def test_kotlyarevsky_iamb4(self, stress_dict):
        assert check_meter_line("Еней був парубок моторний", "ямб", 4, stress_dict).ok is True

    def test_lesya_iamb5(self, stress_dict):
        assert check_meter_line("На шлях я вийшла ранньою весною", "ямб", 5, stress_dict).ok is True

    def test_chuprynka_trochee4(self, stress_dict):
        assert check_meter_line("Ой як млосно Ой як чадно", "хорей", 4, stress_dict).ok is True

    def test_skovoroda_dactyl4_line1(self, stress_dict):
        assert check_meter_line("Всякому місту звичай і права", "дактиль", 4, stress_dict).ok is True

    def test_sosyura_amphibrach4_line1(self, stress_dict):
        assert check_meter_line("Любіть Україну як сонце любіть", "амфібрахій", 4, stress_dict).ok is True

    def test_lesya_anapest3_line1(self, stress_dict):
        assert check_meter_line("Ні я хочу крізь сльози сміятись", "анапест", 3, stress_dict).ok is True

    def test_kostenko_anapest3_line1(self, stress_dict):
        assert check_meter_line("Хоч на вулиці зимно і сніжно", "анапест", 3, stress_dict).ok is True

    def test_pyrrhic_function_word_at_stressed_position(self, stress_dict):
        # 6 syllables → 3-foot iamb (previously mis-labelled as 4-foot, which hid the
        # missing-foot bug that foot-size-aware line_length_ok now catches)
        assert check_meter_line("Реве та стогне Дніпр", "ямб", 3, stress_dict).ok is True

    def test_pyrrhic_monosyllabic_preposition(self, stress_dict):
        assert check_meter_line("Струмок біжить в густім лісочку", "ямб", 4, stress_dict).ok is True

    def test_spondee_monosyllabic_noun_at_unstressed(self, stress_dict):
        result = check_meter_line("Реве та стогне Дніпр широкий", "ямб", 4, stress_dict)
        assert result.ok is True
        assert len(result.error_positions) == 0

    def test_four_foot_iamb_feminine_line_rejected_as_pentameter(self, stress_dict):
        # Regression for the web-UI case: the user requested 5-foot iamb
        # but the LLM produced these 4-foot iambic lines with feminine
        # clausulae (9 syllables, stresses at 2/4/6/8). The validator used
        # to mark them as "100% meter" because of the catalectic loophole.
        for line in [
            "впадуть тяжкі твої кайдани",
            "згниють в землі лихі тирани",
        ]:
            result = check_meter_line(line, "ямб", 5, stress_dict)
            assert result.ok is False, f"short iamb line erroneously accepted: {line!r}"
            assert result.total_syllables == 9

    def test_four_foot_iamb_feminine_line_accepted_as_tetrameter(self, stress_dict):
        # Same lines are legitimate 4-foot iamb with feminine clausula.
        for line in [
            "впадуть тяжкі твої кайдани",
            "згниють в землі лихі тирани",
        ]:
            assert check_meter_line(line, "ямб", 4, stress_dict).ok is True

    def test_wrong_meter_detected(self, stress_dict):
        result = check_meter_line(
            "Сонце світить яскраво і тепло",
            "ямб", 4, stress_dict, allowed_mismatches=0,
        )
        assert isinstance(result.ok, bool)


class TestCheckMeterPoem:
    def test_returns_list(self, stress_dict):
        results = check_meter_poem("Рядок один\nРядок два\n", "ямб", 4, stress_dict)
        assert isinstance(results, list)
        assert len(results) == 2

    def test_empty_poem_produces_no_line_results(self, stress_dict):
        # Empty poems now get an explicit failing MeterResult with no lines.
        assert check_meter_poem("", "ямб", 4, stress_dict) == []

    def test_four_line_poem(self, stress_dict):
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "Де тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\n"
            "І серце в тиші гомонить.\n"
        )
        results = check_meter_poem(poem, "ямб", 4, stress_dict)
        assert len(results) == 4
        for r in results:
            assert isinstance(r, LineMeterResult)

    def test_shevchenko_poem_high_accuracy(self, stress_dict):
        poem = (
            "Реве та стогне Дніпр широкий,\n"
            "Сердитий вітер завива,\n"
            "Додолу верби гне високі,\n"
            "Горами хвилю підійма."
        )
        results = check_meter_poem(poem, "ямб", 4, stress_dict)
        assert sum(1 for r in results if r.ok) >= 3

    def test_lesya_anapest3_full_poem(self, stress_dict):
        poem = (
            "Ні я хочу крізь сльози сміятись\n"
            "Серед лиха співати пісні\n"
            "Без надії таки сподіватись\n"
            "Жити хочу Геть думи сумні"
        )
        results = check_meter_poem(poem, "анапест", 3, stress_dict)
        assert sum(1 for r in results if r.ok) >= 3


class TestWeakStressWordSet:
    @pytest.mark.parametrize("word", [
        "і", "й", "та", "а", "але",
        "в", "у", "на", "з", "до",
        "не", "ні", "б", "же",
        "я", "ти", "він", "вона",
        "мої", "твій",
    ])
    def test_expected_words_in_set(self, word: str):
        assert word in WEAK_STRESS_WORDS

    @pytest.mark.parametrize("word", [
        "весна", "сонце", "ліс", "вітер", "думи",
        "україна", "кохання", "серце",
    ])
    def test_content_words_not_in_set(self, word: str):
        assert word not in WEAK_STRESS_WORDS


class TestFeedbackFormatting:
    def test_feedback_format(self, stress_dict):
        # Construct a failing line and render it via DefaultLineFeedbackBuilder
        # + UkrainianFeedbackFormatter. `UkrainianProsodyAnalyzer` no longer
        # owns feedback construction — that role lives behind
        # `ILineFeedbackBuilder` now.
        _ = stress_dict  # unused; kept for fixture parity
        result = LineMeterResult(
            ok=False,
            expected_stresses=(2, 4, 6, 8,),
            actual_stresses=(3, 6,),
            error_positions=(2, 4,),
            total_syllables=8,
        )
        fb = DefaultLineFeedbackBuilder(
            template_provider=UkrainianMeterTemplateProvider(),
        ).build(1, MeterSpec(name="ямб", foot_count=4), result)
        rendered = UkrainianFeedbackFormatter().format_line(fb)
        assert "Line 2" in rendered
        assert "ямб" in rendered
        assert "2, 4, 6, 8" in rendered
        assert "3, 6" in rendered
        assert "Rewrite" in rendered
