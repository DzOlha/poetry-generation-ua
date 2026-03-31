from __future__ import annotations

from dataclasses import dataclass

from src.meter.stress import StressDict
from src.meter.validator import MeterCheckResult, check_meter_poem
from src.rhyme.validator import RhymeCheckResult, check_rhyme

# ---------------------------------------------------------------------------
# Meter Accuracy
# ---------------------------------------------------------------------------

def meter_accuracy(
    poem_text: str, meter: str, foot_count: int, stress_dict: StressDict, allowed_mismatches: int = 2
) -> float:
    results = check_meter_poem(
        poem_text, meter=meter, foot_count=foot_count, stress_dict=stress_dict, allowed_mismatches=allowed_mismatches
    )
    if not results:
        return 1.0
    return sum(1 for r in results if r.ok) / len(results)


# ---------------------------------------------------------------------------
# Rhyme Accuracy
# ---------------------------------------------------------------------------

def rhyme_accuracy(poem_text: str, scheme: str, stress_dict: StressDict, threshold: float = 0.7) -> float:
    result = check_rhyme(poem_text, scheme=scheme, stress_dict=stress_dict, threshold=threshold)
    if not result.pairs:
        return 1.0
    return sum(1 for p in result.pairs if p.rhyme_ok) / len(result.pairs)


# ---------------------------------------------------------------------------
# Regeneration Success Rate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegenerationStats:
    initial_meter_violations: int
    final_meter_violations: int
    initial_rhyme_violations: int
    final_rhyme_violations: int
    meter_fixed: int
    rhyme_fixed: int
    success_rate: float


def regeneration_success_rate(
    initial_meter_results: list[MeterCheckResult],
    final_meter_results: list[MeterCheckResult],
    initial_rhyme_result: RhymeCheckResult,
    final_rhyme_result: RhymeCheckResult,
) -> RegenerationStats:
    init_m_violations = sum(1 for r in initial_meter_results if not r.ok)
    final_m_violations = sum(1 for r in final_meter_results if not r.ok)

    init_r_violations = sum(1 for p in initial_rhyme_result.pairs if not p.rhyme_ok)
    final_r_violations = sum(1 for p in final_rhyme_result.pairs if not p.rhyme_ok)

    meter_fixed = max(0, init_m_violations - final_m_violations)
    rhyme_fixed = max(0, init_r_violations - final_r_violations)

    total_initial = init_m_violations + init_r_violations
    total_fixed = meter_fixed + rhyme_fixed
    rate = total_fixed / total_initial if total_initial > 0 else 1.0

    return RegenerationStats(
        initial_meter_violations=init_m_violations,
        final_meter_violations=final_m_violations,
        initial_rhyme_violations=init_r_violations,
        final_rhyme_violations=final_r_violations,
        meter_fixed=meter_fixed,
        rhyme_fixed=rhyme_fixed,
        success_rate=rate,
    )


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationReport:
    meter_accuracy_pct: float
    rhyme_accuracy_pct: float


def evaluate_poem(
    poem_text: str,
    meter: str,
    foot_count: int,
    rhyme_scheme: str,
    stress_dict: StressDict,
) -> EvaluationReport:
    m_acc = meter_accuracy(poem_text, meter=meter, foot_count=foot_count, stress_dict=stress_dict)
    r_acc = rhyme_accuracy(poem_text, scheme=rhyme_scheme, stress_dict=stress_dict)

    return EvaluationReport(
        meter_accuracy_pct=m_acc * 100.0,
        rhyme_accuracy_pct=r_acc * 100.0,
    )
