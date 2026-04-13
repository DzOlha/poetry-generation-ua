"""Logging port."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ILogger(ABC):
    """Minimal structured logger abstraction."""

    @abstractmethod
    def info(self, message: str, **fields: Any) -> None: ...

    @abstractmethod
    def warning(self, message: str, **fields: Any) -> None: ...

    @abstractmethod
    def error(self, message: str, **fields: Any) -> None: ...
