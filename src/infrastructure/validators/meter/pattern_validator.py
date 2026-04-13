"""Pattern-based Ukrainian meter validator."""
from __future__ import annotations

from src.domain.models import LineMeterResult, MeterSpec
from src.domain.ports import (
    ILineFeedbackBuilder,
    IProsodyAnalyzer,
    ITextProcessor,
)
from src.infrastructure.validators.meter.base import BaseMeterValidator


class PatternMeterValidator(BaseMeterValidator):
    """Validates meter by direct pattern matching with tolerance rules.

    Algorithm:
      1. Build expected stress pattern from meter template × foot count.
      2. Compute actual stress pattern from words via IProsodyAnalyzer.
      3. Count real errors (mismatches that are not tolerable pyrrhics/spondees).
      4. A line passes if real_errors ≤ allowed_mismatches AND length is OK.
    """

    def __init__(
        self,
        prosody: IProsodyAnalyzer,
        text_processor: ITextProcessor,
        feedback_builder: ILineFeedbackBuilder,
        allowed_mismatches: int = 2,
    ) -> None:
        super().__init__(
            prosody=prosody,
            text_processor=text_processor,
            feedback_builder=feedback_builder,
            allowed_mismatches=allowed_mismatches,
        )

    def _validate_line(self, line: str, meter: MeterSpec) -> LineMeterResult:
        tokens = self._text.tokenize_line(line)
        words = list(tokens.words)
        syllables = list(tokens.syllables_per_word)
        actual = self._prosody.actual_stress_pattern(words, syllables)
        expected = self._prosody.build_expected_pattern(meter.name, meter.foot_count)
        flags = self._prosody.syllable_word_flags(words, syllables)

        n = min(len(actual), len(expected))
        raw_errors = [i for i in range(n) if actual[i] != expected[i]]
        real_errors = [
            pos for pos in raw_errors
            if not self._prosody.is_tolerated_mismatch(pos, actual, expected, flags)
        ]

        length_ok = self._prosody.line_length_ok(len(actual), len(expected), actual)
        ok = len(real_errors) <= self.allowed_mismatches and length_ok

        return LineMeterResult(
            ok=ok,
            expected_stresses=tuple(i + 1 for i, v in enumerate(expected) if v == "—"),
            actual_stresses=tuple(i + 1 for i, v in enumerate(actual) if v == "—"),
            error_positions=tuple(p + 1 for p in real_errors),
            total_syllables=len(actual),
        )
