"""LLM call tracing port.

Lets callers peek inside the decorator stack and see what the real
provider returned BEFORE extraction/sanitization touched it. Designed
for debugging — when sanitized output reaches the validator but looks
suspicious, the recorder answers "was the garbage already in the raw
LLM response, or did we corrupt it in post-processing?".

Each LLM call (``generate`` / ``regenerate_lines``) updates the
recorder with the three observable stages. Callers that want to
attach the snapshot to a trace record read it immediately after the
call returns. The recorder keeps only the most recent call — snapshots
are overwritten on every new invocation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMCallSnapshot:
    """Text observed at each decorator layer for a single LLM call."""

    raw: str = ""
    extracted: str = ""
    sanitized: str = ""


class ILLMCallRecorder(ABC):
    """Captures per-layer output of the most recent LLM call."""

    @abstractmethod
    def record_raw(self, text: str) -> None: ...

    @abstractmethod
    def record_extracted(self, text: str) -> None: ...

    @abstractmethod
    def record_sanitized(self, text: str) -> None: ...

    @abstractmethod
    def snapshot(self) -> LLMCallSnapshot: ...
