"""Unit tests for BruteForceRhymeDetector."""
from __future__ import annotations

from src.config import DetectionConfig
from src.domain.models import RhymeResult, RhymeScheme
from src.domain.ports.validation import IRhymeValidator
from src.infrastructure.detection import BruteForceRhymeDetector


class _FixedAccuracyValidator(IRhymeValidator):
    """Returns a fixed accuracy for one specific scheme, 0.0 for all others."""

    def __init__(self, target_scheme: str, accuracy: float) -> None:
        self._target = target_scheme
        self._accuracy = accuracy

    def validate(self, poem_text: str, scheme: RhymeScheme) -> RhymeResult:
        if scheme.pattern == self._target:
            return RhymeResult(ok=True, accuracy=self._accuracy)
        return RhymeResult(ok=False, accuracy=0.0)


class TestBruteForceRhymeDetector:
    def test_detects_abab(self) -> None:
        validator = _FixedAccuracyValidator("ABAB", 0.9)
        detector = BruteForceRhymeDetector(
            rhyme_validator=validator,
            config=DetectionConfig(rhyme_min_accuracy=0.75),
        )
        result = detector.detect("dummy text")
        assert result is not None
        assert result.scheme == "ABAB"
        assert result.accuracy == 0.9

    def test_returns_none_below_threshold(self) -> None:
        validator = _FixedAccuracyValidator("ABAB", 0.5)
        detector = BruteForceRhymeDetector(
            rhyme_validator=validator,
            config=DetectionConfig(rhyme_min_accuracy=0.75),
        )
        result = detector.detect("dummy text")
        assert result is None

    def test_default_config_surfaces_scheme_for_single_solid_pair(self) -> None:
        # Regression for the user-reported "душу/мусиш" case: in a quatrain
        # one rhyme pair can be slant and score below the pair threshold,
        # leaving aggregate accuracy at 0.5. The default detection cutoff
        # must still surface the scheme — requiring 0.75 would silently
        # demand both pairs be exact.
        validator = _FixedAccuracyValidator("ABAB", 0.5)
        detector = BruteForceRhymeDetector(
            rhyme_validator=validator,
            config=DetectionConfig(),  # use production default
        )
        result = detector.detect("dummy text")
        assert result is not None
        assert result.scheme == "ABAB"
        assert result.accuracy == 0.5

    def test_zero_accuracy_still_rejected(self) -> None:
        # Looser detection must still reject poems with no rhyme signal at
        # all, otherwise every input gets a spurious scheme.
        validator = _FixedAccuracyValidator("ABAB", 0.0)
        detector = BruteForceRhymeDetector(
            rhyme_validator=validator,
            config=DetectionConfig(),
        )
        assert detector.detect("dummy text") is None

    def test_picks_highest_accuracy(self) -> None:
        class _MultiValidator(IRhymeValidator):
            def validate(self, poem_text: str, scheme: RhymeScheme) -> RhymeResult:
                if scheme.pattern == "AABB":
                    return RhymeResult(ok=True, accuracy=0.95)
                if scheme.pattern == "ABAB":
                    return RhymeResult(ok=True, accuracy=0.80)
                return RhymeResult(ok=False, accuracy=0.0)

        detector = BruteForceRhymeDetector(
            rhyme_validator=_MultiValidator(),
            config=DetectionConfig(rhyme_min_accuracy=0.75),
        )
        result = detector.detect("dummy text")
        assert result is not None
        assert result.scheme == "AABB"
