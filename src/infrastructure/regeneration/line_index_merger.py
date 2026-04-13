"""Structured merger that splices regenerated lines back into the original poem.

Unlike the old regex-based merger, this implementation reads line indices
directly from the structured LineFeedback/PairFeedback objects, so the LLM
feedback-string format is free to change without breaking merging.
"""
from __future__ import annotations

from src.domain.feedback import LineFeedback, PairFeedback
from src.domain.ports import IRegenerationMerger


class LineIndexMerger(IRegenerationMerger):
    """Merges regenerated output back into the original poem via line indices.

    Strategy:
      1. If the LLM returned the full poem (same line count), use it as-is.
      2. Otherwise, collect violation line indices from the structured feedback.
      3. Splice each regenerated line into the original at its violation index.

    Line indices come from LineFeedback.line_idx and PairFeedback.line_b_idx
    (the rhyme merger always rewrites the B line of a pair).
    """

    def merge(
        self,
        original: str,
        regenerated: str,
        meter_feedback: tuple[LineFeedback, ...],
        rhyme_feedback: tuple[PairFeedback, ...],
    ) -> str:
        original_lines = [ln for ln in original.strip().splitlines() if ln.strip()]
        regen_lines = [ln for ln in regenerated.strip().splitlines() if ln.strip()]

        if len(regen_lines) == len(original_lines):
            return regenerated  # Full poem returned — use as-is.

        violation_indices: set[int] = set()
        for f in meter_feedback:
            if 0 <= f.line_idx < len(original_lines):
                violation_indices.add(f.line_idx)
        for pf in rhyme_feedback:
            if 0 <= pf.line_b_idx < len(original_lines):
                violation_indices.add(pf.line_b_idx)

        if not violation_indices or len(regen_lines) < len(violation_indices):
            return regenerated  # Cannot safely merge — use regenerated.

        result = list(original_lines)
        for i, orig_idx in enumerate(sorted(violation_indices)):
            if i < len(regen_lines):
                result[orig_idx] = regen_lines[i]
        return "\n".join(result) + "\n"
