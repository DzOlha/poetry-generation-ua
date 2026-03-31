from __future__ import annotations

from src.evaluation.metrics import (
    EvaluationReport,
    RegenerationStats,
    evaluate_poem,
    meter_accuracy,
    regeneration_success_rate,
    rhyme_accuracy,
)
from src.meter.stress import StressDict
from src.meter.validator import MeterCheckResult
from src.rhyme.validator import RhymeCheckResult


class TestMeterAccuracy:
    def test_returns_float(self, stress_dict: StressDict):
        poem = "Весна прийшла у ліс зелений,\nДе тінь і світло гомонить.\n"
        acc = meter_accuracy(poem, "ямб", 4, stress_dict)
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

    def test_empty_poem(self, stress_dict: StressDict):
        assert meter_accuracy("", "ямб", 4, stress_dict) == 1.0


class TestRhymeAccuracy:
    def test_returns_float(self, stress_dict: StressDict):
        poem = "ліс\nвіс\nріс\nніс\n"
        acc = rhyme_accuracy(poem, "AABB", stress_dict)
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

    def test_empty_poem(self, stress_dict: StressDict):
        assert rhyme_accuracy("", "ABAB", stress_dict) == 1.0


class TestRegenerationSuccessRate:
    def test_all_fixed(self):
        initial_meter = [
            MeterCheckResult(ok=False, expected_stress_syllables_1based=[], actual_stress_syllables_1based=[],
                             errors_positions_1based=[1], total_syllables=4),
            MeterCheckResult(ok=False, expected_stress_syllables_1based=[], actual_stress_syllables_1based=[],
                             errors_positions_1based=[2], total_syllables=4),
        ]
        final_meter = [
            MeterCheckResult(ok=True, expected_stress_syllables_1based=[], actual_stress_syllables_1based=[],
                             errors_positions_1based=[], total_syllables=4),
            MeterCheckResult(ok=True, expected_stress_syllables_1based=[], actual_stress_syllables_1based=[],
                             errors_positions_1based=[], total_syllables=4),
        ]
        initial_rhyme = RhymeCheckResult(is_valid=True, pairs=[])
        final_rhyme = RhymeCheckResult(is_valid=True, pairs=[])

        stats = regeneration_success_rate(initial_meter, final_meter, initial_rhyme, final_rhyme)
        assert isinstance(stats, RegenerationStats)
        assert stats.success_rate == 1.0
        assert stats.meter_fixed == 2

    def test_none_fixed(self):
        initial_meter = [
            MeterCheckResult(ok=False, expected_stress_syllables_1based=[], actual_stress_syllables_1based=[],
                             errors_positions_1based=[1], total_syllables=4),
        ]
        final_meter = [
            MeterCheckResult(ok=False, expected_stress_syllables_1based=[], actual_stress_syllables_1based=[],
                             errors_positions_1based=[1], total_syllables=4),
        ]
        initial_rhyme = RhymeCheckResult(is_valid=True, pairs=[])
        final_rhyme = RhymeCheckResult(is_valid=True, pairs=[])

        stats = regeneration_success_rate(initial_meter, final_meter, initial_rhyme, final_rhyme)
        assert stats.success_rate == 0.0

    def test_no_violations(self):
        stats = regeneration_success_rate(
            [], [], RhymeCheckResult(is_valid=True, pairs=[]), RhymeCheckResult(is_valid=True, pairs=[])
        )
        assert stats.success_rate == 1.0


class TestEvaluatePoem:
    def test_returns_evaluation_report(self, stress_dict: StressDict):
        poem = (
            "Весна прийшла у ліс зелений,\nДе тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\nІ серце в тиші гомонить.\n"
        )
        report = evaluate_poem(
            poem_text=poem,
            meter="ямб",
            foot_count=4,
            rhyme_scheme="ABAB",
            stress_dict=stress_dict,
        )
        assert isinstance(report, EvaluationReport)
        assert 0.0 <= report.meter_accuracy_pct <= 100.0
        assert 0.0 <= report.rhyme_accuracy_pct <= 100.0
