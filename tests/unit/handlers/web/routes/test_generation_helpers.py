"""Unit tests for UI-rendering helpers in `handlers.web.routes.generation`.

These helpers build the per-line display data used by the annotated poem
view (coloured syllables + length notes). The tests cover vowel tagging,
pairing of non-empty lines with meter results, and the length-difference
note text.
"""
from __future__ import annotations

from src.domain.models import LineMeterResult
from src.handlers.shared.line_displays import (
    line_displays as _line_displays,
)
from src.handlers.shared.line_displays import (
    line_segments as _line_segments,
)


class TestLineSegments:
    def test_empty_line_yields_empty_segments(self) -> None:
        assert _line_segments("", expected=set(), actual=set()) == []

    def test_consonants_untagged(self) -> None:
        segs = _line_segments("бвг", expected=set(), actual=set())
        assert all(s["tag"] == "" for s in segs)
        assert [s["ch"] for s in segs] == ["б", "в", "г"]

    def test_vowel_marked_expected_only(self) -> None:
        # "мама": vowels at syllable positions 1 ("а") and 2 ("а").
        segs = _line_segments("мама", expected={1}, actual=set())
        vowel_segs = [s for s in segs if s["ch"] == "а"]
        assert vowel_segs[0]["tag"] == "exp"
        assert vowel_segs[1]["tag"] == ""

    def test_vowel_marked_actual_only(self) -> None:
        segs = _line_segments("мама", expected=set(), actual={2})
        vowels = [s for s in segs if s["tag"] != ""]
        # First vowel untagged, second is the actual-stress syllable.
        assert vowels == [{"ch": "а", "tag": "act"}]

    def test_vowel_marked_both_when_expected_and_actual_agree(self) -> None:
        segs = _line_segments("мама", expected={2}, actual={2})
        vowels = [s for s in segs if s["tag"] != ""]
        assert vowels[-1]["tag"] == "both"

    def test_case_insensitive_vowel_detection(self) -> None:
        segs = _line_segments("Ма", expected={1}, actual=set())
        vowels = [s for s in segs if s["tag"] != ""]
        assert vowels and vowels[0]["ch"] == "а"
        # Uppercase "М" is not a vowel.
        assert segs[0]["tag"] == ""

    def test_apostrophe_and_hyphen_not_vowels(self) -> None:
        segs = _line_segments("м'я-та", expected={1, 2}, actual=set())
        vowels = [s for s in segs if s["tag"] != ""]
        # Only "я" and "а" are vowels.
        assert [s["ch"] for s in vowels] == ["я", "а"]


class TestLineDisplays:
    @staticmethod
    def _result(
        *,
        ok: bool = True,
        expected: tuple[int, ...] = (2, 4),
        actual: tuple[int, ...] = (2, 4),
        total: int = 4,
        errors: tuple[int, ...] = (),
        annotation: str = "",
    ) -> LineMeterResult:
        return LineMeterResult(
            ok=ok,
            expected_stresses=expected,
            actual_stresses=actual,
            error_positions=errors,
            total_syllables=total,
            annotation=annotation,
        )

    def test_blank_lines_become_blank_entries(self) -> None:
        poem = "рядок один\n\nрядок два"
        displays = _line_displays(poem, (self._result(), self._result()))
        # Middle blank line preserved as a blank entry so stanza layout
        # doesn't collapse in the UI.
        assert [d.get("blank", False) for d in displays] == [False, True, False]

    def test_non_empty_lines_pair_with_results_in_order(self) -> None:
        poem = "перший\nдругий"
        r1 = self._result(ok=True)
        r2 = self._result(ok=False)
        displays = _line_displays(poem, (r1, r2))
        assert displays[0]["ok"] is True
        assert displays[1]["ok"] is False
        assert displays[0]["text"] == "перший"
        assert displays[1]["text"] == "другий"

    def test_extra_lines_without_results_render_without_segments(self) -> None:
        poem = "а\nб"
        displays = _line_displays(poem, (self._result(),))
        # First line paired; second line has no result so it falls through
        # to a plain text fallback without segments.
        assert displays[0].get("segments") is not None
        assert displays[1].get("segments") is None

    def test_length_note_when_actual_shorter(self) -> None:
        # 4-foot iamb expects 8 syllables, actual line has 4
        result = LineMeterResult(
            ok=False,
            expected_stresses=(2, 4, 6, 8),
            actual_stresses=(2, 4),
            error_positions=(),
            total_syllables=4,
        )
        displays = _line_displays("мама тата", (result,))
        note = str(displays[0]["length_note"])
        assert "коротше" in note and "(8)" in note

    def test_length_note_when_actual_longer(self) -> None:
        # 2-foot iamb expects 4 syllables, actual line has 6
        result = LineMeterResult(
            ok=False,
            expected_stresses=(2, 4),
            actual_stresses=(2, 4, 6),
            error_positions=(),
            total_syllables=6,
        )
        displays = _line_displays("рядочок довгий", (result,))
        note = str(displays[0]["length_note"])
        assert "довше" in note and "(4)" in note

    def test_length_note_empty_when_lengths_match(self) -> None:
        displays = _line_displays("рядок", (self._result(),))
        assert displays[0]["length_note"] == ""

    def test_segments_mark_all_three_tag_kinds(self) -> None:
        # "мама": 2 vowels; expect position 1 expected, position 2 both.
        result = self._result(expected=(1, 2), actual=(2,), total=2)
        displays = _line_displays("мама", (result,))
        segments = displays[0]["segments"]
        assert isinstance(segments, list)
        tagged = [s["tag"] for s in segments if s["tag"]]
        assert tagged == ["exp", "both"]

    def test_annotation_carried_through(self) -> None:
        result = self._result(annotation="BSP score 0.72")
        displays = _line_displays("рядок", (result,))
        assert displays[0]["annotation"] == "BSP score 0.72"

    def test_catalexis_no_length_note(self) -> None:
        # 4-foot iamb feminine ending: 9 syllables instead of 8, but ok=True
        result = self._result(
            ok=True,
            expected=(2, 4, 6, 8),
            actual=(2, 4, 6, 8),
            total=9,
        )
        displays = _line_displays("рядочок", (result,))
        assert displays[0]["length_note"] == ""

    def test_catalectic_truncation_no_length_note(self) -> None:
        # Trochee catalexis: 7 syllables instead of 8, but ok=True
        result = self._result(
            ok=True,
            expected=(1, 3, 5, 7),
            actual=(1, 3, 5, 7),
            total=7,
        )
        displays = _line_displays("рядочок", (result,))
        assert displays[0]["length_note"] == ""

    def test_length_note_only_when_not_ok(self) -> None:
        # Same diff but ok=True → no note; ok=False → note
        result_ok = self._result(
            ok=True, expected=(2, 4, 6, 8), actual=(2, 4), total=4,
        )
        result_bad = self._result(
            ok=False, expected=(2, 4, 6, 8), actual=(2, 4), total=4,
        )
        assert _line_displays("рядок", (result_ok,))[0]["length_note"] == ""
        assert _line_displays("рядок", (result_bad,))[0]["length_note"] != ""

    def test_expected_len_computed_from_foot_size(self) -> None:
        # Dactyl 3-foot: stresses at (1, 4, 7), foot_size=3, expected=9
        result = self._result(
            ok=False, expected=(1, 4, 7), actual=(1,), total=5,
        )
        displays = _line_displays("рядочок", (result,))
        note = str(displays[0]["length_note"])
        assert "(9)" in note

    def test_catalectic_length_with_stress_mismatch_reports_stresses(self) -> None:
        # Amphibrach 3-foot expects 9 syllables (stresses at 2, 5, 8). A
        # catalectic line has 8 syllables — acceptable length range is
        # [max_stress=8 ; expected_len + foot_size-1 = 11]. If the line has
        # 8 syllables but actual stresses don't land on (2, 5, 8), the note
        # must explain stress mismatch rather than misleadingly say "1
        # syllable shorter" — which was the bug.
        result = self._result(
            ok=False,
            expected=(2, 5, 8),
            actual=(2, 4, 6),  # wrong stress positions
            total=8,
        )
        displays = _line_displays("І тисне сліпа німота", (result,))
        note = str(displays[0]["length_note"])
        assert "коротше" not in note
        assert "наголоси" in note

    def test_actual_too_short_still_reports_length(self) -> None:
        # Truly short line (last stress doesn't fit) — must still report as
        # a length problem, not a stress one.
        result = self._result(
            ok=False,
            expected=(2, 5, 8),
            actual=(2,),
            total=4,  # 4 < max_stress_pos=8 → really short
        )
        displays = _line_displays("тільки два", (result,))
        note = str(displays[0]["length_note"])
        assert "коротше" in note and "(9)" in note
