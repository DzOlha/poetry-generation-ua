"""`ExtractingLLMProvider` — peels the final poem out of a sentinel envelope.

Sits just outside the real provider and just inside the sanitizer. The
model is instructed (via the prompt builders) to emit its final poem
between ``<POEM>...</POEM>`` tags; this decorator pulls the content out
and discards surrounding chain-of-thought. If the envelope is missing
the extractor returns the input unchanged so the downstream sanitizer
can still try to salvage it.

The decorator also pushes the raw provider response and the
post-extraction text into an ``ILLMCallRecorder`` so callers can
inspect what the model literally returned — the sanitizer is the last
place where the raw text is still accessible, everywhere downstream
only sees the cleaned version.
"""
from __future__ import annotations

from src.domain.ports import ILLMCallRecorder, ILLMProvider, IPoemExtractor


class ExtractingLLMProvider(ILLMProvider):
    """Delegates to ``IPoemExtractor`` on every LLM response."""

    def __init__(
        self,
        inner: ILLMProvider,
        extractor: IPoemExtractor,
        recorder: ILLMCallRecorder,
    ) -> None:
        self._inner = inner
        self._extractor = extractor
        self._recorder = recorder

    def generate(self, prompt: str) -> str:
        return self._run(self._inner.generate(prompt))

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self._run(self._inner.regenerate_lines(poem, feedback))

    def _run(self, raw: str) -> str:
        self._recorder.record_raw(raw)
        extracted = self._extractor.extract(raw)
        self._recorder.record_extracted(extracted)
        return extracted
