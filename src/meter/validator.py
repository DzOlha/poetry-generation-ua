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

# Ukrainian service words (prepositions, conjunctions, particles) and
# weakly-stressed pronouns that are typically unstressed in poetic speech.
# These syllables are allowed in metrically "strong" positions (pyrrhic substitution)
# and their unexpected stress at "weak" positions is also allowed (spondee substitution).
_UA_WEAK_STRESS_WORDS: frozenset[str] = frozenset({
    # Prepositions
    "в", "у", "на", "з", "зі", "зо", "до", "від", "за", "під", "над",
    "між", "через", "по", "про", "без", "при", "для", "із", "об",
    "перед", "після", "навколо", "крізь", "поміж", "серед", "поза", "коло",
    # Conjunctions
    "і", "й", "та", "а", "але", "чи", "або", "якщо", "коли", "що", "як",
    "бо", "хоч", "хоча", "зате", "ані", "проте", "однак", "якби", "поки",
    "доки", "щоб", "аби", "ніж", "мов", "немов", "наче", "неначе", "мовби",
    "нібито", "тому", "отже", "адже", "тобто",
    # Particles
    "не", "ні", "б", "би", "же", "ж", "то", "хай", "нехай",
    "лише", "лиш", "тільки", "саме", "навіть", "ось", "он", "аж", "ще",
    "вже", "теж", "також",
    # Personal pronouns (often weakly stressed in poetry)
    "я", "ти", "він", "вона", "воно", "ми", "ви", "вони",
    "мене", "тебе", "його", "її", "нас", "вас", "них",
    # Possessive pronouns (frequently unstressed in metrical context)
    "мій", "моя", "моє", "мої", "твій", "твоя", "твоє", "твої",
    "свій", "своя", "своє", "свої",
    # Demonstrative
    "це", "те",
})


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


def _syllable_word_flags(words: list[str], syllables_per_word: list[int]) -> list[tuple[bool, bool]]:
    """Return per-syllable (is_monosyllabic, is_weak_stress_word) flags."""
    flags: list[tuple[bool, bool]] = []
    for w, syl in zip(words, syllables_per_word):
        if syl <= 0:
            continue
        is_mono = syl == 1
        is_weak = w.lower() in _UA_WEAK_STRESS_WORDS
        for _ in range(syl):
            flags.append((is_mono, is_weak))
    return flags


def _line_length_ok(actual_len: int, expected_len: int, actual: list[str]) -> bool:
    """Allow feminine endings (+1-2 unstressed syllables) and catalectic lines (-1 to -3 syllables).

    Feminine ending: one extra unstressed syllable at the end (дієслівне / жіноче).
    Dactylic ending: two extra unstressed syllables at the end (дактилічне).
    Catalectic (-1 to -3): truncated final foot — common in folk and classical Ukrainian verse,
    e.g., a dactyl 3ft line alternating with a catalectic 2ft line (differs by one full foot = 3 syl).
    """
    diff = actual_len - expected_len
    if diff == 0:
        return True
    if diff == 1:
        return actual[-1] == "u"  # feminine ending
    if diff == 2:
        return actual[-2] == "u" and actual[-1] == "u"  # dactylic ending
    if -3 <= diff <= -1:
        return True  # catalectic (truncated final foot; covers 2- and 3-syllable foot patterns)
    return False


def _is_tolerated_mismatch(pos_0based: int, actual: list[str], expected: list[str],
                            flags: list[tuple[bool, bool]]) -> bool:
    """Return True if mismatch at pos_0based is a valid pyrrhic or spondee substitution.

    Pyrrhic (пірихій): expected stress '—' but actual unstressed 'u' — tolerated when
    the syllable belongs to a monosyllabic word or a weak-stress word (prepositions,
    conjunctions, particles, weakly-stressed pronouns).

    Spondee (спондей): expected unstressed 'u' but actual stressed '—' — tolerated when
    the syllable belongs to a monosyllabic word (secondary/contrastive stress is natural).
    """
    if pos_0based >= len(actual) or pos_0based >= len(expected):
        return False
    exp = expected[pos_0based]
    act = actual[pos_0based]
    if exp == act:
        return False
    if pos_0based >= len(flags):
        return False
    is_mono, is_weak = flags[pos_0based]
    if exp == "—" and act == "u":
        # Pyrrhic: missing stress — tolerated for monosyllabic or function/weak words
        return is_mono or is_weak
    if exp == "u" and act == "—":
        # Spondee: extra stress — tolerated for monosyllabic words
        return is_mono or is_weak
    return False


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
    flags = _syllable_word_flags(tokens.words, tokens.syllables_per_word)

    n = min(len(actual), len(expected))
    raw_errors: list[int] = [i + 1 for i in range(n) if actual[i] != expected[i]]

    # Filter out tolerated pyrrhic and spondee substitutions
    real_errors: list[int] = [
        pos for pos in raw_errors
        if not _is_tolerated_mismatch(pos - 1, actual, expected, flags)
    ]

    length_ok = _line_length_ok(len(actual), len(expected), actual)
    ok = len(real_errors) <= allowed_mismatches and length_ok

    expected_stress = [i + 1 for i, v in enumerate(expected) if v == "—"]
    actual_stress = [i + 1 for i, v in enumerate(actual) if v == "—"]

    return MeterCheckResult(
        ok=ok,
        expected_stress_syllables_1based=expected_stress,
        actual_stress_syllables_1based=actual_stress,
        errors_positions_1based=real_errors,
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
    expected_syl = (
        max(result.expected_stress_syllables_1based) if result.expected_stress_syllables_1based else 0
    )
    syl_note = ""
    if result.total_syllables != expected_syl:
        diff = result.total_syllables - expected_syl
        direction = f"shorten by {diff}" if diff > 0 else f"lengthen by {-diff}"
        syl_note = f"\nLine has {result.total_syllables} syllables but should have ~{expected_syl} ({direction})."
    return (
        f"Line {line_idx_0based + 1} violates {meter} meter.\n"
        f"Expected stress on syllables: {expected}.\n"
        f"Actual stress on syllables: {actual}."
        f"{syl_note}\n"
        "Rewrite only this line, keep the meaning."
    )
