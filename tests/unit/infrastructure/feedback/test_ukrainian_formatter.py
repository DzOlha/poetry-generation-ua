"""Tests for UkrainianFeedbackFormatter."""
from __future__ import annotations

from src.domain.feedback import LineFeedback, PairFeedback
from src.infrastructure.feedback import UkrainianFeedbackFormatter


class TestFormatLine:
    def test_contains_line_number_one_based(self):
        fb = LineFeedback(
            line_idx=2, meter_name="ямб", foot_count=4,
            expected_stresses=(2, 4, 6, 8), actual_stresses=(3, 6),
            total_syllables=8,
        )
        msg = UkrainianFeedbackFormatter().format_line(fb)
        assert "Line 3" in msg  # 0-based idx 2 → "Line 3"
        assert "ямб" in msg
        assert "2, 4, 6, 8" in msg

    def test_includes_syllable_note_when_mismatched(self):
        fb = LineFeedback(
            line_idx=0, meter_name="ямб", foot_count=4,
            expected_stresses=(2, 4, 6, 8), actual_stresses=(2, 4),
            total_syllables=6,  # short by 2
        )
        msg = UkrainianFeedbackFormatter().format_line(fb)
        assert "syllables" in msg

    def test_extra_note_included(self):
        fb = LineFeedback(
            line_idx=0, meter_name="ямб", foot_count=4,
            expected_stresses=(), actual_stresses=(), total_syllables=0,
            extra_note=" (BSP score: 0.42)",
        )
        msg = UkrainianFeedbackFormatter().format_line(fb)
        assert "BSP score" in msg


class TestFormatPair:
    def test_contains_both_line_numbers(self):
        fb = PairFeedback(
            line_a_idx=0, line_b_idx=2, scheme_pattern="ABAB",
            word_a="ліс", word_b="вітер",
            rhyme_part_a="is", rhyme_part_b="iter",
            score=0.23,
        )
        msg = UkrainianFeedbackFormatter().format_pair(fb)
        assert "Lines 1 and 3" in msg
        assert "ABAB" in msg
        assert "0.23" in msg
        assert "Rewrite line 3" in msg


class TestFormatAll:
    def test_meter_first_then_rhyme(self):
        line_fb = LineFeedback(
            line_idx=0, meter_name="ямб", foot_count=4,
            expected_stresses=(2,), actual_stresses=(1,), total_syllables=4,
        )
        pair_fb = PairFeedback(
            line_a_idx=0, line_b_idx=1, scheme_pattern="AABB",
            word_a="a", word_b="b", rhyme_part_a="a", rhyme_part_b="b", score=0.0,
        )
        from src.domain.ports import format_all_feedback
        msgs = format_all_feedback(UkrainianFeedbackFormatter(), (line_fb,), (pair_fb,))
        assert len(msgs) == 2
        assert "Line 1" in msgs[0]
        assert "Lines 1 and 2" in msgs[1]
