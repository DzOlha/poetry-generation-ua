"""Real-time adapters for ``IClock`` / ``IDelayer`` backed by ``time``."""
from __future__ import annotations

import time

from src.domain.ports.clock import IClock, IDelayer


class SystemClock(IClock):
    """Monotonic clock backed by ``time.perf_counter``."""

    def now(self) -> float:
        return time.perf_counter()


class SystemDelayer(IDelayer):
    """Sleep adapter backed by ``time.sleep``."""

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
