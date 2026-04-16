"""Ukrainian prosody analyzer — facade composing focused collaborators.

The analyser owns pure prosody concerns: expected pattern generation,
actual pattern extraction from tokenised lines, per-position tolerance
rules, and line-length tolerance. Feedback construction is delegated to
`ILineFeedbackBuilder` so the analyser stays SRP-clean.
"""
from __future__ import annotations

from src.domain.ports import (
    IMeterTemplateProvider,
    IProsodyAnalyzer,
    IStressResolver,
    ISyllableFlagStrategy,
    IWeakStressLexicon,
)


class UkrainianProsodyAnalyzer(IProsodyAnalyzer):
    """IProsodyAnalyzer facade composing template + flag + stress collaborators."""

    def __init__(
        self,
        template_provider: IMeterTemplateProvider,
        flag_strategy: ISyllableFlagStrategy,
        stress_resolver: IStressResolver,
        weak_stress_lexicon: IWeakStressLexicon,
    ) -> None:
        self._templates = template_provider
        self._flags = flag_strategy
        self._stress = stress_resolver
        self._weak = weak_stress_lexicon

    # ------------------------------------------------------------------
    # IProsodyAnalyzer
    # ------------------------------------------------------------------

    def build_expected_pattern(self, meter: str, foot_count: int) -> list[str]:
        foot = self._templates.template_for(meter)
        return (foot * foot_count).copy()

    def actual_stress_pattern(
        self,
        words: list[str],
        syllables_per_word: list[int],
    ) -> list[str]:
        total = sum(syllables_per_word)
        pattern = ["u"] * total
        cursor = 0
        for w, syl in zip(words, syllables_per_word):
            if syl <= 0:
                continue
            if syl == 1 and self._weak.is_weak(w):
                cursor += syl
                continue
            s_idx = self._stress.resolve(w)
            s_idx = min(max(0, s_idx), syl - 1)
            pattern[cursor + s_idx] = "—"
            cursor += syl
        return pattern

    def syllable_word_flags(
        self,
        words: list[str],
        syllables_per_word: list[int],
    ) -> list[tuple[bool, bool]]:
        return self._flags.flags(words, syllables_per_word)

    def line_length_ok(
        self,
        actual_pattern: list[str],
        expected_pattern: list[str],
    ) -> bool:
        diff = len(actual_pattern) - len(expected_pattern)
        if diff == 0:
            return True
        if diff == 1:
            return actual_pattern[-1] == "u"
        if diff == 2:
            return actual_pattern[-2] == "u" and actual_pattern[-1] == "u"
        if diff >= 0:
            return False
        # Negative diff: accept only catalectic truncation, i.e. dropping
        # trailing *unstressed* positions of the expected pattern. A dropped
        # "—" means an actual stress position was cut off — that is a
        # genuine foot-count error (e.g. a 4-foot iambic line with a
        # feminine clausula, which would otherwise be silently accepted as
        # a short 5-foot line). A full missing foot is rejected by the
        # foot-size bound below.
        foot_size = self._foot_size(expected_pattern)
        if not -foot_size < diff < 0:
            return False
        dropped = expected_pattern[len(actual_pattern):]
        return all(s == "u" for s in dropped)

    @staticmethod
    def _foot_size(expected_pattern: list[str]) -> int:
        stress_positions = [i for i, s in enumerate(expected_pattern) if s == "—"]
        if len(stress_positions) >= 2:
            return stress_positions[1] - stress_positions[0]
        return len(expected_pattern) or 2

    def is_tolerated_mismatch(
        self,
        pos: int,
        actual: list[str],
        expected: list[str],
        flags: list[tuple[bool, bool]],
    ) -> bool:
        if pos >= len(actual) or pos >= len(expected) or pos >= len(flags):
            return False
        if actual[pos] == expected[pos]:
            return False
        is_mono, is_weak = flags[pos]
        return is_mono or is_weak
