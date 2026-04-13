"""Ukrainian stress dictionary — concrete IStressDictionary implementation.

Wraps the `ukrainian-word-stress` library. If the library cannot be loaded
the constructor logs a warning and `get_stress_index` returns None; the
injected `IStressResolver` then applies the penultimate-vowel fallback.
This behaviour is explicit and observable: production callers can inspect
the logger to see when the real engine is unavailable.
"""
from __future__ import annotations

from src.domain.ports import ILogger, IStressDictionary
from src.shared.text_utils_ua import VOWELS_UA


class UkrainianStressDict(IStressDictionary):
    """Assigns stress to Ukrainian words using the ukrainian-word-stress library.

    Args:
        logger:       Injected ILogger used to warn when the backend is missing.
        on_ambiguity: Strategy for homograph disambiguation —
                      'first' (default), 'last', or 'random'.
    """

    def __init__(self, logger: ILogger, on_ambiguity: str = "first") -> None:
        self.on_ambiguity = on_ambiguity
        self._accent = "\u0301"  # combining acute accent
        self._stressify = None
        self._logger: ILogger = logger
        try:
            from ukrainian_word_stress import Stressifier, StressSymbol
            self._stressify = Stressifier(
                stress_symbol=StressSymbol.CombiningAcuteAccent,
                on_ambiguity=self.on_ambiguity,
            )
        except Exception as exc:
            self._logger.warning(
                "ukrainian-word-stress backend unavailable; falling back to heuristic",
                error=str(exc),
            )
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
