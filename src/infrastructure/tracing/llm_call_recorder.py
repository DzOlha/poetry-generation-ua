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
    """Stores the most-recent raw/extracted/sanitized text + token usage."""

    def __init__(self) -> None:
        self._raw = ""
        self._extracted = ""
        self._sanitized = ""
        self._input_tokens = 0
        self._output_tokens = 0

    def record_raw(self, text: str) -> None:
        self._raw = text
        # Wipe downstream-stage text so a stale extracted/sanitized value
        # from a previous call cannot surface if those stages are skipped.
        # Token counts are intentionally NOT reset here: the LLM provider
        # calls record_usage() before returning the raw text, so clearing
        # tokens here would erase the data that was just captured.
        self._extracted = ""
        self._sanitized = ""

    def record_extracted(self, text: str) -> None:
        self._extracted = text

    def record_sanitized(self, text: str) -> None:
        self._sanitized = text

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self._input_tokens = max(0, int(input_tokens))
        self._output_tokens = max(0, int(output_tokens))

    def snapshot(self) -> LLMCallSnapshot:
        return LLMCallSnapshot(
            raw=self._raw,
            extracted=self._extracted,
            sanitized=self._sanitized,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


class NullLLMCallRecorder(ILLMCallRecorder):
    """Recorder that discards every call — default for test doubles."""

    def record_raw(self, text: str) -> None: ...
    def record_extracted(self, text: str) -> None: ...
    def record_sanitized(self, text: str) -> None: ...
    def record_usage(self, input_tokens: int, output_tokens: int) -> None: ...

    def snapshot(self) -> LLMCallSnapshot:
        return LLMCallSnapshot()
