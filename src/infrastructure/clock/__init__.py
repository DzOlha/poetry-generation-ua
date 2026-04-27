"""System clock and delayer — concrete adapters wrapping ``time``."""
from __future__ import annotations

from src.infrastructure.clock.system_clock import SystemClock, SystemDelayer

__all__ = ["SystemClock", "SystemDelayer"]
