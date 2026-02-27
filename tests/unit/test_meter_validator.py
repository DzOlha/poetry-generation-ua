from __future__ import annotations

import pytest

from src.meter.stress import StressDict
from src.meter.validator import (
    MeterCheckResult,
    build_expected_pattern,
    check_meter_line,
    check_meter_poem,
    meter_feedback,
)


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
        assert build_expected_pattern(meter, foot_count) == expected

    def test_unsupported_meter_raises(self):
        with pytest.raises(ValueError, match="Unsupported meter"):
            build_expected_pattern("невідомий", 4)

    def test_case_insensitive(self):
        assert build_expected_pattern("Ямб", 2) == ["u", "—", "u", "—"]
        assert build_expected_pattern("IAMB", 2) == ["u", "—", "u", "—"]


class TestCheckMeterLine:
    def test_returns_meter_check_result(self, stress_dict: StressDict):
        result = check_meter_line("Весна прийшла у ліс", "ямб", 4, stress_dict)
        assert isinstance(result, MeterCheckResult)

    def test_result_has_required_fields(self, stress_dict: StressDict):
        result = check_meter_line("Весна прийшла у ліс", "ямб", 4, stress_dict)
        assert isinstance(result.ok, bool)
        assert isinstance(result.expected_stress_syllables_1based, list)
        assert isinstance(result.actual_stress_syllables_1based, list)
        assert isinstance(result.errors_positions_1based, list)
        assert isinstance(result.total_syllables, int)
        assert result.total_syllables > 0


class TestCheckMeterPoem:
    def test_returns_list(self, stress_dict: StressDict):
        poem = "Рядок один\nРядок два\n"
        results = check_meter_poem(poem, "ямб", 4, stress_dict)
        assert isinstance(results, list)
        assert len(results) == 2

    def test_empty_poem(self, stress_dict: StressDict):
        results = check_meter_poem("", "ямб", 4, stress_dict)
        assert results == []

    def test_four_line_poem(self, stress_dict: StressDict):
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "Де тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\n"
            "І серце в тиші гомонить.\n"
        )
        results = check_meter_poem(poem, "ямб", 4, stress_dict)
        assert len(results) == 4
        for r in results:
            assert isinstance(r, MeterCheckResult)


class TestMeterFeedback:
    def test_feedback_format(self):
        result = MeterCheckResult(
            ok=False,
            expected_stress_syllables_1based=[2, 4, 6, 8],
            actual_stress_syllables_1based=[3, 6],
            errors_positions_1based=[2, 4],
            total_syllables=8,
        )
        fb = meter_feedback(1, "ямб", result)
        assert "Line 2" in fb
        assert "ямб" in fb
        assert "2, 4, 6, 8" in fb
        assert "3, 6" in fb
        assert "Rewrite" in fb
