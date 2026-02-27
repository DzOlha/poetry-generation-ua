from __future__ import annotations

from dataclasses import dataclass

from src.meter.stress import StressDict, get_stress_index_safe
from src.rhyme.transcribe import rhyme_part_from_stress
from src.utils.distance import normalized_similarity
from src.utils.text import extract_words_ua, split_nonempty_lines


@dataclass(frozen=True)
class RhymePairResult:
    line_1: int
    line_2: int
    word_1: str
    word_2: str
    rhyme_part_1: str
    rhyme_part_2: str
    score: float
    rhyme_ok: bool


@dataclass(frozen=True)
class RhymeCheckResult:
    is_valid: bool
    pairs: list[RhymePairResult]


def _pairs_for_scheme(scheme: str, n_lines: int) -> list[tuple[int, int]]:
    s = scheme.strip().upper()
    if s == "AABB":
        return [(0, 1), (2, 3)] if n_lines >= 4 else []
    if s == "ABAB":
        return [(0, 2), (1, 3)] if n_lines >= 4 else []
    if s == "ABBA":
        return [(0, 3), (1, 2)] if n_lines >= 4 else []
    if s == "AAAA":
        return [(i, j) for i in range(n_lines) for j in range(i + 1, n_lines)]
    raise ValueError(f"Unsupported rhyme scheme: {scheme}")


def _last_word(line: str) -> str | None:
    words = extract_words_ua(line)
    return words[-1] if words else None


def rhyme_score(word1: str, word2: str, stress_dict: StressDict) -> tuple[str, str, float]:
    s1 = get_stress_index_safe(word1, stress_dict)
    s2 = get_stress_index_safe(word2, stress_dict)
    r1 = rhyme_part_from_stress(word1, s1)
    r2 = rhyme_part_from_stress(word2, s2)
    score = normalized_similarity(r1, r2)
    return r1, r2, score


def check_rhyme(poem_text: str, scheme: str, stress_dict: StressDict, threshold: float = 0.7) -> RhymeCheckResult:
    lines = split_nonempty_lines(poem_text)
    pairs = _pairs_for_scheme(scheme, len(lines))

    results: list[RhymePairResult] = []
    for a, b in pairs:
        w1 = _last_word(lines[a]) or ""
        w2 = _last_word(lines[b]) or ""
        r1, r2, score = rhyme_score(w1, w2, stress_dict)
        ok = score >= threshold
        results.append(
            RhymePairResult(
                line_1=a + 1,
                line_2=b + 1,
                word_1=w1,
                word_2=w2,
                rhyme_part_1=r1,
                rhyme_part_2=r2,
                score=score,
                rhyme_ok=ok,
            )
        )

    return RhymeCheckResult(is_valid=all(p.rhyme_ok for p in results), pairs=results)


def rhyme_feedback(pair: RhymePairResult, scheme: str) -> str:
    return (
        f"Lines {pair.line_1} and {pair.line_2} should rhyme (scheme {scheme}).\n"
        f"Expected rhyme with ending '{pair.rhyme_part_1}'.\n"
        f"Current ending '{pair.rhyme_part_2}' does not match (score: {pair.score:.2f}).\n"
        f"Rewrite line {pair.line_2} keeping the meaning and meter."
    )
