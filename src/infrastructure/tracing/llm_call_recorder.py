"""In-memory ``ILLMCallRecorder`` adapters.

``InMemoryLLMCallRecorder`` is the real recorder — each ``record_*``
call overwrites the stored text, so ``snapshot()`` always reflects the
most recent LLM invocation. ``NullLLMCallRecorder`` is the zero-cost
adapter used by test doubles that do not care about tracing.

Both live under ``infrastructure.tracing`` because the feature is
observability-adjacent and keeps the existing ``StageTimer`` company.
"""
from __future__ import annotations

from src.domain.ports import ILLMCallRecorder, LLMCallSnapshot


class InMemoryLLMCallRecorder(ILLMCallRecorder):
    """Stores the most-recent raw/extracted/sanitized text in memory."""

    def __init__(self) -> None:
        self._raw = ""
        self._extracted = ""
        self._sanitized = ""

    def record_raw(self, text: str) -> None:
        self._raw = text
        # A fresh raw recording marks a new LLM call; wipe the downstream
        # stages so a stale snapshot from a previous call cannot surface
        # if the extractor/sanitizer are not invoked this time around.
        self._extracted = ""
        self._sanitized = ""

    def record_extracted(self, text: str) -> None:
        self._extracted = text

    def record_sanitized(self, text: str) -> None:
        self._sanitized = text

    def snapshot(self) -> LLMCallSnapshot:
        return LLMCallSnapshot(
            raw=self._raw,
            extracted=self._extracted,
            sanitized=self._sanitized,
        )


class NullLLMCallRecorder(ILLMCallRecorder):
    """Recorder that discards every call — default for test doubles."""

    def record_raw(self, text: str) -> None: ...
    def record_extracted(self, text: str) -> None: ...
    def record_sanitized(self, text: str) -> None: ...

    def snapshot(self) -> LLMCallSnapshot:
        return LLMCallSnapshot()
