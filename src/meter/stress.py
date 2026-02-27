from __future__ import annotations

from dataclasses import dataclass

from src.utils.text import VOWELS_UA, count_syllables_ua


@dataclass
class StressDict:
    on_ambiguity: str = "first"

    def __post_init__(self) -> None:
        self._stressify = None
        self._accent = "\u0301"
        try:
            from ukrainian_word_stress import Stressifier, StressSymbol

            self._stressify = Stressifier(
                stress_symbol=StressSymbol.CombiningAcuteAccent,
                on_ambiguity=self.on_ambiguity,
            )
        except Exception:
            self._stressify = None

    def get_stress_index(self, word: str) -> int | None:
        if not self._stressify:
            return None
        stressed = self._stressify(word)
        vowel_idx = 0
        for i, ch in enumerate(stressed):
            if ch.lower() in VOWELS_UA:
                if i + 1 < len(stressed) and stressed[i + 1] == self._accent:
                    return vowel_idx
                vowel_idx += 1
        return None


def get_stress_index_safe(word: str, stress_dict: StressDict) -> int:
    idx = stress_dict.get_stress_index(word)
    if idx is not None:
        return idx
    syllables = count_syllables_ua(word)
    return max(0, syllables - 1)
