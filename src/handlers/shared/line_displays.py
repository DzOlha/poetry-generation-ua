"""Per-line display helpers — shared between HTML and JSON API handlers.

Pairs raw poem lines with `LineMeterResult` data and produces a structured,
serialisable description of each line: char-level segments tagged by stress
role (expected / actual / both), plus a human-readable length note.

Used by the web templates to render the annotated poem, and by the JSON
API schemas to expose the same data so an SPA can reproduce the UI without
duplicating the stress-position math on the client.
"""
from __future__ import annotations

from src.domain.models import LineMeterResult
from src.shared.text_utils_ua import VOWELS_UA


def line_segments(
    text: str,
    expected: set[int],
    actual: set[int],
) -> list[dict[str, object]]:
    """Split a line into char-level segments, tagging the k-th vowel with its stress role."""
    segments: list[dict[str, object]] = []
    vowel_idx = 0
    for ch in text:
        if ch.lower() in VOWELS_UA:
            vowel_idx += 1
            exp = vowel_idx in expected
            act = vowel_idx in actual
            if exp and act:
                tag = "both"
            elif exp:
                tag = "exp"
            elif act:
                tag = "act"
            else:
                tag = ""
            segments.append({"ch": ch, "tag": tag})
        else:
            segments.append({"ch": ch, "tag": ""})
    return segments


def line_displays(
    poem_text: str,
    line_results: tuple[LineMeterResult, ...],
) -> list[dict[str, object]]:
    """Pair raw poem lines with their per-line meter results for UI rendering."""
    results = iter(line_results)
    displays: list[dict[str, object]] = []
    for raw in poem_text.splitlines():
        text = raw.strip()
        if not text:
            displays.append({"blank": True})
            continue
        result = next(results, None)
        if result is None:
            displays.append({"blank": False, "text": text, "segments": None})
            continue
        expected_set = set(result.expected_stresses)
        actual_set = set(result.actual_stresses)
        stresses = sorted(result.expected_stresses)
        if len(stresses) >= 2:
            foot_size = stresses[1] - stresses[0]
            expected_len = foot_size * len(stresses)
        else:
            expected_len = max(stresses, default=0)
        actual_len = result.total_syllables
        diff = actual_len - expected_len
        # A line's length is "plausible" for the meter when the last expected
        # stress still fits AND the line isn't more than one foot longer than
        # the full pattern — this covers catalexis (trailing unstressed syls
        # dropped) and feminine endings. When the line fits that window but
        # still failed validation, the issue is STRESS POSITIONS, not length
        # — and saying "1 syllable shorter" would be misleading.
        max_stress_pos = max(stresses, default=0)
        length_plausible = (
            max_stress_pos <= actual_len <= expected_len + max(foot_size - 1, 0)
            if len(stresses) >= 2
            else actual_len == expected_len
        )
        if not result.ok and diff > 0 and not length_plausible:
            length_note = f"на {diff} склад(и/ів) довше очікуваного ({expected_len})"
        elif not result.ok and diff < 0 and not length_plausible:
            length_note = f"на {-diff} склад(и/ів) коротше очікуваного ({expected_len})"
        elif not result.ok and expected_set != actual_set:
            length_note = "наголоси не збігаються з очікуваним метром"
        else:
            length_note = ""
        displays.append({
            "blank": False,
            "text": text,
            "ok": result.ok,
            "segments": line_segments(text, expected_set, actual_set),
            "length_note": length_note,
            "annotation": result.annotation,
        })
    return displays
