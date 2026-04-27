"""Clock and delayer ports — abstract time and sleep so services stay pure.

`IClock` exposes a monotonic timer used by services to measure elapsed
duration of pipeline runs. `IDelayer` exposes a sleep primitive used by
the batch evaluator to throttle calls between LLM requests.

Concrete `SystemClock` / `SystemDelayer` adapters live in
``src.infrastructure.clock`` and wrap ``time.perf_counter`` / ``time.sleep``.
Tests inject `FakeClock` / `FakeDelayer` doubles so the service contract
can be exercised without touching the real wall clock.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IClock(ABC):
    """Monotonic time source.  Returns seconds with sub-millisecond resolution."""

    @abstractmethod
    def now(self) -> float:
        """Return a monotonically increasing timestamp in seconds."""


class IDelayer(ABC):
    """Cooperative sleep primitive.  Used to throttle external calls."""

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        """Block the current thread for ``seconds`` seconds."""
