"""Wall-clock timer for pipeline stages.

Extracted from the domain layer since `time.perf_counter()` is an
infrastructure concern (system clock dependency).
"""
from __future__ import annotations

import time
from typing import Any


class StageTimer:
    """Context manager that measures wall-clock time for a stage."""

    def __init__(self) -> None:
        self.elapsed: float = 0.0
        self._t0: float = 0.0

    def __enter__(self) -> StageTimer:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed = time.perf_counter() - self._t0
