"""IFeedbackFormatter adapter that renders structured feedback into Ukrainian/English prompts.

The natural-language string produced here is what the LLM sees during the
regeneration prompt. It intentionally embeds the 0-based → 1-based line index
in the literal `"Line N"` format so both humans and the LLM can spot the
position. The IRegenerationMerger does NOT parse this text; it reads the
structured LineFeedback/PairFeedback objects directly.
"""
from __future__ import annotations

from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.ports import IFeedbackFormatter


class UkrainianFeedbackFormatter(IFeedbackFormatter):
    """Renders LineFeedback/PairFeedback into the same prompt style the LLM is trained on."""

    def format_line(self, fb: LineFeedback) -> str:
        expected = ", ".join(str(p) for p in fb.expected_stresses)
        actual = ", ".join(str(p) for p in fb.actual_stresses)
        syl_note = ""
        expected_syllables = max(fb.expected_stresses) if fb.expected_stresses else 0
        if expected_syllables and fb.total_syllables != expected_syllables:
            diff = fb.total_syllables - expected_syllables
            direction = f"shorten by {diff}" if diff > 0 else f"lengthen by {-diff}"
            syl_note = (
                f"\nLine has {fb.total_syllables} syllables"
                f" but should have ~{expected_syllables} ({direction})."
            )
        extra = fb.extra_note if fb.extra_note else ""
        return (
            f"Line {fb.line_idx + 1} violates {fb.meter_name} meter{extra}.\n"
            f"Expected stress on syllables: {expected}.\n"
            f"Actual stress on syllables: {actual}."
            f"{syl_note}\n"
            "Rewrite only this line, keep the meaning."
        )

    def format_pair(self, fb: PairFeedback) -> str:
        clausula_note = ""
        if fb.clausula_a.value != "unknown" and fb.clausula_b.value != "unknown":
            clausula_note = (
                f"\nClausula: line {fb.line_a_idx + 1} is {fb.clausula_a.value}, "
                f"line {fb.line_b_idx + 1} is {fb.clausula_b.value}."
            )

        precision_note = ""
        if fb.precision.value != "none":
            precision_note = f"\nRhyme type detected: {fb.precision.value}."

        return (
            f"Lines {fb.line_a_idx + 1} and {fb.line_b_idx + 1} "
            f"should rhyme (scheme {fb.scheme_pattern}).\n"
            f"Expected rhyme with ending '{fb.rhyme_part_a}'.\n"
            f"Current ending '{fb.rhyme_part_b}' does not match "
            f"(score: {fb.score:.2f})."
            f"{clausula_note}"
            f"{precision_note}\n"
            f"Rewrite line {fb.line_b_idx + 1} keeping the meaning and meter."
        )
