"""`SanitizingLLMProvider` — strips reasoning/scansion from LLM output.

Sits inside the retry/timeout/logging decorators and outside the
extractor + real provider. Every outer layer observes the cleaned text,
so retry attempts always produce sanitized output.

If the sanitizer removes every line the underlying response was pure
chain-of-thought. We treat that as a transient failure and raise
``LLMError`` so the retry layer can ask the model for another attempt;
silently returning garbage would let the bad response reach the
validator and surface as misleading metric/rhyme complaints.
"""
from __future__ import annotations

from src.domain.errors import LLMError
from src.domain.ports import ILLMCallRecorder, ILLMProvider, IPoemOutputSanitizer


class SanitizingLLMProvider(ILLMProvider):
    """Applies ``IPoemOutputSanitizer`` to every LLM response."""

    def __init__(
        self,
        inner: ILLMProvider,
        sanitizer: IPoemOutputSanitizer,
        recorder: ILLMCallRecorder,
    ) -> None:
        self._inner = inner
        self._sanitizer = sanitizer
        self._recorder = recorder

    def generate(self, prompt: str) -> str:
        return self._run(self._inner.generate(prompt), op="generate")

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self._run(
            self._inner.regenerate_lines(poem, feedback), op="regenerate_lines",
        )

    def _run(self, extracted: str, *, op: str) -> str:
        sanitized = self._sanitizer.sanitize(extracted)
        # Record even empty results so the trace surfaces "sanitizer
        # dropped everything" instead of leaving callers guessing.
        self._recorder.record_sanitized(sanitized)
        if sanitized and sanitized.strip():
            return sanitized
        raise LLMError(
            f"LLM {op} produced no valid poem lines after sanitization "
            f"(response was pure reasoning/scansion)",
        )
