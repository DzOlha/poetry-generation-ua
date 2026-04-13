"""Runner port."""
from __future__ import annotations

from abc import ABC, abstractmethod


class IRunner(ABC):
    """Encapsulates a top-level program execution flow."""

    @abstractmethod
    def run(self) -> int: ...
