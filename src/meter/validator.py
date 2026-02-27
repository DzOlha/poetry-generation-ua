from __future__ import annotations

from dataclasses import dataclass

from src.meter.stress import StressDict, get_stress_index_safe
from src.utils.text import split_nonempty_lines, tokenize_line_ua


_METER_TEMPLATES: dict[str, list[str]] = {
    "ямб": ["u", "—"],
    "iamb": ["u", "—"],
    "хорей": ["—", "u"],
    "trochee": ["—", "u"],
    "дактиль": ["—", "u", "u"],
    "dactyl": ["—", "u", "u"],
    "амфібрахій": ["u", "—", "u"],
    "amphibrach": ["u", "—", "u"],
    "анапест": ["u", "u", "—"],
    "anapest": ["u", "u", "—"],
}


@dataclass(frozen=True)
class MeterCheckResult:
    ok: bool
    expected_stress_syllables_1based: list[int]
    actual_stress_syllables_1based: list[int]
    errors_positions_1based: list[int]
    total_syllables: int


def build_expected_pattern(meter: str, foot_count: int) -> list[str]:
    key = meter.strip().lower()
    if key not in _METER_TEMPLATES:
        raise ValueError(f"Unsupported meter: {meter}")
    foot = _METER_TEMPLATES[key]
    return (foot * foot_count).copy()


def _actual_stress_pattern(words: list[str], syllables_per_word: list[int], stress_dict: StressDict) -> list[str]:
    total = sum(syllables_per_word)
    pattern = ["u"] * total
    cursor = 0
    for w, syl in zip(words, syllables_per_word):
        if syl <= 0:
            continue
        s_idx = get_stress_index_safe(w, stress_dict)
        s_idx = min(max(0, s_idx), syl - 1)
        pattern[cursor + s_idx] = "—"
        cursor += syl
    return pattern


def check_meter_line(
    line: str,
    meter: str,
    foot_count: int,
    stress_dict: StressDict,
    allowed_mismatches: int = 2,
) -> MeterCheckResult:
    tokens = tokenize_line_ua(line)
    actual = _actual_stress_pattern(tokens.words, tokens.syllables_per_word, stress_dict)
    expected = build_expected_pattern(meter, foot_count)

    n = min(len(actual), len(expected))
    errors: list[int] = [i + 1 for i in range(n) if actual[i] != expected[i]]
    ok = len(errors) <= allowed_mismatches and len(actual) == len(expected)

    expected_stress = [i + 1 for i, v in enumerate(expected) if v == "—"]
    actual_stress = [i + 1 for i, v in enumerate(actual) if v == "—"]

    return MeterCheckResult(
        ok=ok,
        expected_stress_syllables_1based=expected_stress,
        actual_stress_syllables_1based=actual_stress,
        errors_positions_1based=errors,
        total_syllables=len(actual),
    )


def check_meter_poem(
    poem_text: str,
    meter: str,
    foot_count: int,
    stress_dict: StressDict,
    allowed_mismatches: int = 2,
) -> list[MeterCheckResult]:
    lines = split_nonempty_lines(poem_text)
    return [
        check_meter_line(
            line=ln,
            meter=meter,
            foot_count=foot_count,
            stress_dict=stress_dict,
            allowed_mismatches=allowed_mismatches,
        )
        for ln in lines
    ]


def meter_feedback(line_idx_0based: int, meter: str, result: MeterCheckResult) -> str:
    expected = ", ".join(map(str, result.expected_stress_syllables_1based))
    actual = ", ".join(map(str, result.actual_stress_syllables_1based))
    return (
        f"Line {line_idx_0based + 1} violates {meter} meter.\n"
        f"Expected stress on syllables: {expected}.\n"
        f"Actual stress on syllables: {actual}.\n"
        "Rewrite only this line, keep the meaning."
    )
