"""`TimeoutLLMProvider` — enforces a hard deadline on any LLM call.

Wraps an inner `ILLMProvider` and runs each call on a daemon thread with a
`threading.Event` as the join marker. If the call does not complete within
`timeout_sec`, the decorator raises `LLMError` so the retry decorator (or
the upstream pipeline stage) can decide what to do.

Python has no way to forcibly terminate a thread mid-computation, so the
inner call continues in the background until it finishes naturally. That's
the same trade-off any sync HTTP-client timeout has — the caller sees a
deterministic failure, the background thread self-terminates eventually.
"""
from __future__ import annotations

import threading
from collections.abc import Callable

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider


class TimeoutLLMProvider(ILLMProvider):
    """Raises `LLMError` if the inner call exceeds the timeout."""

    def __init__(self, inner: ILLMProvider, timeout_sec: float) -> None:
        if timeout_sec <= 0:
            raise ValueError("timeout_sec must be > 0")
        self._inner = inner
        self._timeout_sec = float(timeout_sec)

    def generate(self, prompt: str) -> str:
        return self._run_with_timeout(
            lambda: self._inner.generate(prompt),
            op="generate",
        )

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self._run_with_timeout(
            lambda: self._inner.regenerate_lines(poem, feedback),
            op="regenerate_lines",
        )

    def _run_with_timeout(self, call: Callable[[], str], *, op: str) -> str:
        result: dict[str, object] = {}

        def runner() -> None:
            try:
                result["value"] = call()
            except BaseException as exc:  # noqa: BLE001 — propagated via result
                result["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join(self._timeout_sec)

        if thread.is_alive():
            raise LLMError(
                f"LLM {op} exceeded timeout of {self._timeout_sec:.1f}s",
            )

        if "error" in result:
            exc = result["error"]
            if isinstance(exc, LLMError):
                raise exc
            # Translate unexpected exceptions into LLMError so the retry
            # decorator treats them uniformly.
            raise LLMError(f"LLM {op} failed: {exc}") from (exc if isinstance(exc, BaseException) else None)

        return str(result["value"])
