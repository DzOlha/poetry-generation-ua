"""Concrete ILogger adapters used across the project.

StdOutLogger       — human-readable stderr output for CLI / scripts.
CollectingLogger   — stores all records in a list for assertion in tests.
NullLogger         — discards every record (default for silent contexts).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import IO, Any

from src.domain.ports import ILogger


@dataclass
class StdOutLogger(ILogger):
    """Writes each log record as a single line to a text stream (default stderr)."""

    stream: IO[str] = field(default_factory=lambda: sys.stderr)
    min_level: str = "info"  # "info" | "warning" | "error"

    _LEVELS = {"info": 0, "warning": 1, "error": 2}

    def info(self, message: str, **fields: Any) -> None:
        self._emit("info", message, fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit("warning", message, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit("error", message, fields)

    def _emit(self, level: str, message: str, fields: dict[str, Any]) -> None:
        if self._LEVELS[level] < self._LEVELS.get(self.min_level, 0):
            return
        suffix = ""
        if fields:
            suffix = " " + " ".join(f"{k}={v!r}" for k, v in fields.items())
        print(f"[{level}] {message}{suffix}", file=self.stream)


@dataclass
class CollectingLogger(ILogger):
    """Stores every record in memory — useful for tests."""

    records: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def info(self, message: str, **fields: Any) -> None:
        self.records.append(("info", message, fields))

    def warning(self, message: str, **fields: Any) -> None:
        self.records.append(("warning", message, fields))

    def error(self, message: str, **fields: Any) -> None:
        self.records.append(("error", message, fields))


class NullLogger(ILogger):
    """Discards every record."""

    def info(self, message: str, **fields: Any) -> None:
        pass

    def warning(self, message: str, **fields: Any) -> None:
        pass

    def error(self, message: str, **fields: Any) -> None:
        pass
