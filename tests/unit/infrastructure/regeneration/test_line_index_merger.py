"""Tests for LineIndexMerger — the structured IRegenerationMerger implementation."""
from __future__ import annotations

from src.domain.feedback import LineFeedback, PairFeedback
from src.infrastructure.regeneration import LineIndexMerger


def _line_fb(idx: int) -> LineFeedback:
    return LineFeedback(
        line_idx=idx, meter_name="ямб", foot_count=4,
        expected_stresses=(2, 4), actual_stresses=(1,),
        total_syllables=4,
    )


def _pair_fb(b_idx: int) -> PairFeedback:
    return PairFeedback(
        line_a_idx=0, line_b_idx=b_idx, scheme_pattern="AABB",
        word_a="a", word_b="b", rhyme_part_a="a", rhyme_part_b="b", score=0.2,
    )


class TestLineIndexMerger:
    def test_full_poem_passthrough(self):
        merger = LineIndexMerger()
        original = "line1\nline2\nline3\nline4\n"
        regenerated = "fixed1\nfixed2\nfixed3\nfixed4\n"
        result = merger.merge(original, regenerated, (_line_fb(0),), ())
        assert result == regenerated  # same line count → passthrough

    def test_partial_regen_spliced_by_line_idx(self):
        merger = LineIndexMerger()
        original = "line1\nline2\nline3\nline4\n"
        regenerated = "FIXED2\n"
        result = merger.merge(original, regenerated, (_line_fb(1),), ())
        assert "line1" in result
        assert "FIXED2" in result
        assert "line3" in result
        assert "line4" in result

    def test_rhyme_feedback_targets_line_b_idx(self):
        merger = LineIndexMerger()
        original = "a\nb\nc\nd\n"
        regenerated = "FIXED\n"
        result = merger.merge(original, regenerated, (), (_pair_fb(2),))
        lines = [ln for ln in result.splitlines() if ln.strip()]
        assert lines[2] == "FIXED"

    def test_empty_feedback_returns_regenerated_unchanged(self):
        merger = LineIndexMerger()
        original = "a\nb\nc\n"
        regenerated = "just one line\n"
        result = merger.merge(original, regenerated, (), ())
        assert result == regenerated

    def test_regen_too_short_falls_back_to_regenerated(self):
        merger = LineIndexMerger()
        original = "a\nb\nc\nd\n"
        regenerated = ""
        result = merger.merge(
            original, regenerated,
            (_line_fb(0), _line_fb(1)), (),
        )
        assert result == regenerated

    def test_keeps_original_when_llm_only_drops_violating_line(self):
        # LLM returned the poem minus line 3 (the violating one) — all
        # regenerated lines are verbatim copies of original lines. Merger
        # must not splice unchanged line1 into the violation slot; it must
        # keep the original poem intact.
        merger = LineIndexMerger()
        original = "line1\nline2\nline3\nline4\n"
        regenerated = "line1\nline2\nline4\n"  # line3 dropped
        result = merger.merge(original, regenerated, (_line_fb(2),), ())
        assert result == original

    def test_subset_fallback_triggers_only_for_exact_copies(self):
        # If even one regenerated line is a genuine rewrite, splice normally.
        merger = LineIndexMerger()
        original = "line1\nline2\nline3\nline4\n"
        regenerated = "line1\nline2-FIXED\nline4\n"
        result = merger.merge(original, regenerated, (_line_fb(1),), ())
        lines = [ln for ln in result.splitlines() if ln.strip()]
        # Splice path replaces line2 (violation idx) with regen_lines[0]="line1"
        assert lines[1] == "line1"
