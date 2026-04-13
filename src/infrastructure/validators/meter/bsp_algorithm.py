"""BSP algorithm — Bidirectional Stress Pyramid math, extracted from BSPMeterValidator.

BSPAlgorithm encapsulates the pure math of the BSP method:
  - Difference pyramid and sum pyramid construction
  - Composite BSP score computation
  - Structured error detection (stress_missing, stress_overflow, rhythm_break)
  - Clausula classification (masculine / feminine / dactylic / hyperdactylic)

Separating BSP math from the validator (SRP) lets both be tested independently
and makes the algorithm swappable — e.g. a weighted BSP variant only needs
to subclass BSPAlgorithm without touching BSPMeterValidator.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BSPIssue:
    """A single metric violation detected by BSP analysis."""
    position: int    # 1-based syllable position
    type: str        # "rhythm_break" | "stress_missing" | "stress_overflow"
    message: str
    suggestion: str


# ---------------------------------------------------------------------------
# BSPAlgorithm
# ---------------------------------------------------------------------------

class BSPAlgorithm:
    """Pure-math Bidirectional Stress Pyramid analyser.

    All public methods are stateless (no instance state): this class acts as a
    namespace for BSP operations and can be instantiated once and shared.

    Composite score weights (default):
      50% alternation score (rhythm regularity)
      20% variation tolerance (avoids monotone patterns)
      15% global stability (deep-level pyramid)
      15% balance score (stress distribution)
    """

    def __init__(
        self,
        alternation_weight: float = 0.50,
        variation_weight: float = 0.20,
        stability_weight: float = 0.15,
        balance_weight: float = 0.15,
    ) -> None:
        self._w_alt = alternation_weight
        self._w_var = variation_weight
        self._w_stb = stability_weight
        self._w_bal = balance_weight

    # ------------------------------------------------------------------
    # Pyramid construction
    # ------------------------------------------------------------------

    def build_difference_pyramid(self, stress: list[int]) -> list[list[int]]:
        """Build the difference (derivative) pyramid from a stress vector."""
        if not stress:
            return []
        pyramid = [list(stress)]
        current = list(stress)
        while len(current) > 1:
            current = [current[i + 1] - current[i] for i in range(len(current) - 1)]
            pyramid.append(current)
        return pyramid

    def build_sum_pyramid(self, stress: list[int]) -> list[list[int]]:
        """Build the sum (integral) pyramid from a stress vector."""
        if not stress:
            return []
        pyramid = [list(stress)]
        current = list(stress)
        while len(current) > 1:
            current = [current[i] + current[i + 1] for i in range(len(current) - 1)]
            pyramid.append(current)
        return pyramid

    # ------------------------------------------------------------------
    # Sub-scores
    # ------------------------------------------------------------------

    def alternation_score(
        self, d: list[list[int]], expected: list[int]
    ) -> float:
        """Measure how well the actual rhythm alternates like the expected pattern."""
        if len(d) < 2 or not expected:
            return 0.0
        d1 = d[1]
        n = min(len(d1), len(expected) - 1)
        if n == 0:
            return 0.0
        exp_t = [expected[i + 1] - expected[i] for i in range(len(expected) - 1)]
        score = 0.0
        for i in range(n):
            et = exp_t[i] if i < len(exp_t) else 0
            at = d1[i]
            if et == 0:
                score += 0.5
            elif (et > 0 and at > 0) or (et < 0 and at < 0):
                score += 1.0
            elif at == 0:
                score += 0.3
        return score / n

    def variation_tolerance(self, d: list[list[int]]) -> float:
        """Penalise overly monotone patterns (all zeros in d1)."""
        if len(d) < 2:
            return 1.0
        d1 = d[1]
        if not d1:
            return 1.0
        zero_ratio = sum(1 for x in d1 if x == 0) / len(d1)
        return max(0.0, 1.0 - max(0.0, zero_ratio - 0.33) * 2.0)

    def global_stability(self, d: list[list[int]]) -> float:
        """Measure stability of deep pyramid levels (variance penalty)."""
        if len(d) < 3:
            return 1.0
        deep_vals = [x for level in d[2:] for x in level]
        if not deep_vals:
            return 1.0
        mean = sum(deep_vals) / len(deep_vals)
        variance = sum((x - mean) ** 2 for x in deep_vals) / len(deep_vals)
        return max(0.0, 1.0 - variance / (len(d) ** 2 + 1))

    def balance_score(self, s: list[list[int]]) -> float:
        """Measure how evenly stresses are distributed across the line."""
        if not s or not s[0]:
            return 0.0
        base = s[0]
        n = len(base)
        total = sum(base)
        ideal = n / 2.0
        return max(0.0, 1.0 - abs(total - ideal) / n)

    # ------------------------------------------------------------------
    # Composite score
    # ------------------------------------------------------------------

    def compute_score(self, stress: list[int], expected: list[int]) -> float:
        """Return the composite BSP score in [0, 1]."""
        if not stress or not expected:
            return 0.0
        n = min(len(stress), len(expected))
        d = self.build_difference_pyramid(stress[:n])
        s = self.build_sum_pyramid(stress[:n])
        score = (
            self._w_alt * self.alternation_score(d, expected[:n])
            + self._w_var * self.variation_tolerance(d)
            + self._w_stb * self.global_stability(d)
            + self._w_bal * self.balance_score(s)
        )
        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Error detection
    # ------------------------------------------------------------------

    def detect_errors(
        self,
        stress: list[int],
        expected: list[int],
        flags: list[tuple[bool, bool]],
    ) -> list[BSPIssue]:
        """Detect metric violations, returning structured BSPIssue objects."""
        issues: list[BSPIssue] = []
        n = min(len(stress), len(expected))

        for i in range(n):
            act, exp = stress[i], expected[i]
            if act == exp:
                continue
            is_mono = flags[i][0] if i < len(flags) else False
            is_weak = flags[i][1] if i < len(flags) else False
            if exp == 1 and act == 0:
                if is_mono or is_weak:
                    continue
                issues.append(BSPIssue(
                    position=i + 1,
                    type="stress_missing",
                    message=f"Syllable {i + 1}: expected stressed (—) but found unstressed (u).",
                    suggestion="Replace word so this syllable carries the stress.",
                ))
            elif exp == 0 and act == 1:
                if is_mono or is_weak:
                    continue
                issues.append(BSPIssue(
                    position=i + 1,
                    type="stress_overflow",
                    message=f"Syllable {i + 1}: expected unstressed (u) but found stressed (—).",
                    suggestion="Replace word so the stress falls elsewhere.",
                ))

        for i in range(len(stress) - 1):
            if (
                stress[i] == 1 and stress[i + 1] == 1
                and not (
                    i < len(expected) and i + 1 < len(expected)
                    and expected[i] == 1 and expected[i + 1] == 1
                )
            ):
                issues.append(BSPIssue(
                    position=i + 1,
                    type="rhythm_break",
                    message=f"Syllables {i + 1}–{i + 2}: consecutive stressed syllables break rhythm.",
                    suggestion="Replace one word to restore the alternating stress pattern.",
                ))
        return issues

    # ------------------------------------------------------------------
    # Clausula classification
    # ------------------------------------------------------------------

    def detect_clausula(self, stress: list[int]) -> str:
        """Classify the line ending: masculine / feminine / dactylic / hyperdactylic."""
        if not stress:
            return "unknown"
        last_stressed = next(
            (i for i in range(len(stress) - 1, -1, -1) if stress[i] == 1), -1
        )
        if last_stressed == -1:
            return "unknown"
        trailing = len(stress) - 1 - last_stressed
        return {0: "masculine", 1: "feminine", 2: "dactylic"}.get(trailing, "hyperdactylic")
