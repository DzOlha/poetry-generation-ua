"""Ukrainian stress dictionary — concrete IStressDictionary implementation.

Wraps the `ukrainian-word-stress` library. If the library cannot be loaded
the constructor logs a warning and `get_stress_index` returns None; the
injected `IStressResolver` then applies the penultimate-vowel fallback.
This behaviour is explicit and observable: production callers can inspect
the logger to see when the real engine is unavailable.

The Stressifier instance (which loads a ~500MB stanza neural model) is
cached at module level so that multiple UkrainianStressDict instances
(e.g. across several composition containers in tests) share the same
backend and do not duplicate the heavy model in memory.
"""
from __future__ import annotations

import threading
from collections.abc import Callable

from src.domain.ports import ILogger, IStressDictionary
from src.shared.text_utils_ua import VOWELS_UA

# Module-level singleton for the heavy Stressifier backend.
_stressifier_lock = threading.Lock()
_stressifier_cache: dict[str, Callable[[str], str] | None] = {}


def _get_stressifier(on_ambiguity: str) -> Callable[[str], str] | None:
    """Return a cached Stressifier for the given ambiguity strategy."""
    if on_ambiguity in _stressifier_cache:
        return _stressifier_cache[on_ambiguity]

    with _stressifier_lock:
        if on_ambiguity in _stressifier_cache:
            return _stressifier_cache[on_ambiguity]
        try:
            from ukrainian_word_stress import Stressifier, StressSymbol
            instance: Callable[[str], str] = Stressifier(
                stress_symbol=StressSymbol.CombiningAcuteAccent,
                on_ambiguity=on_ambiguity,
            )
            _stressifier_cache[on_ambiguity] = instance
            return instance
        except Exception:
            _stressifier_cache[on_ambiguity] = None
            return None


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
        self._logger: ILogger = logger
        self._stressify: Callable[[str], str] | None = _get_stressifier(on_ambiguity)
        if self._stressify is None:
            self._logger.warning(
                "ukrainian-word-stress backend unavailable; falling back to heuristic",
            )

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
