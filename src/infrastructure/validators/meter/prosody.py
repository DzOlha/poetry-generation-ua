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
)


class UkrainianProsodyAnalyzer(IProsodyAnalyzer):
    """IProsodyAnalyzer facade composing template + flag + stress collaborators."""

    def __init__(
        self,
        template_provider: IMeterTemplateProvider,
        flag_strategy: ISyllableFlagStrategy,
        stress_resolver: IStressResolver,
    ) -> None:
        self._templates = template_provider
        self._flags = flag_strategy
        self._stress = stress_resolver

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
        actual_len: int,
        expected_len: int,
        actual_pattern: list[str],
    ) -> bool:
        diff = actual_len - expected_len
        if diff == 0:
            return True
        if diff == 1:
            return actual_pattern[-1] == "u"
        if diff == 2:
            return actual_pattern[-2] == "u" and actual_pattern[-1] == "u"
        return -3 <= diff <= -1

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
