"""`LoggingLLMProvider` — emits structured log lines around each LLM call.

Goes on the outside of the decorator stack so it observes the caller's
original arguments and the final success/failure (after retries, timeouts,
and any inner errors). Logging is delegated to an injected `ILogger`, so
tests can use a silent logger without suppressing real output.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider, ILogger


class LoggingLLMProvider(ILLMProvider):
    """Logs attempt + duration + error for every LLM call."""

    def __init__(self, inner: ILLMProvider, logger: ILogger) -> None:
        self._inner = inner
        self._logger: ILogger = logger

    def generate(self, prompt: str) -> str:
        return self._log_call(
            lambda: self._inner.generate(prompt),
            op="generate",
            prompt_chars=len(prompt),
        )

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self._log_call(
            lambda: self._inner.regenerate_lines(poem, feedback),
            op="regenerate_lines",
            poem_chars=len(poem),
            feedback_items=len(feedback),
        )

    def _log_call(self, call: Callable[[], str], *, op: str, **fields: Any) -> str:
        t0 = time.perf_counter()
        try:
            result = call()
        except LLMError as exc:
            self._logger.error(
                "LLM call failed",
                op=op,
                duration_sec=round(time.perf_counter() - t0, 3),
                error=str(exc),
                **fields,
            )
            raise
        self._logger.info(
            "LLM call ok",
            op=op,
            duration_sec=round(time.perf_counter() - t0, 3),
            output_chars=len(result),
            **fields,
        )
        return result
