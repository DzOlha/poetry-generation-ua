"""Output sanitization and extraction ports.

Two complementary extension points for cleaning raw LLM output:

``IPoemExtractor`` — pulls the final poem out of a wrapping envelope
(e.g. ``<POEM>...</POEM>`` sentinels) that the model is instructed to
emit. Positive-format instructions like "wrap the result in tags" are
followed far more reliably than negative ones like "do not output
scansion", so extraction is the first line of defence.

``IPoemOutputSanitizer`` — line-level fallback that strips reasoning,
scansion, English commentary, and similar leak-through when the model
skips or malforms the sentinels, or leaks garbage between them.

Kept as separate ports so either strategy can be swapped on its own
(learned classifier, LLM self-critique, alternative envelope format)
without touching the LLM decorator stack.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IPoemExtractor(ABC):
    """Extracts the final poem block from a wrapping envelope.

    Implementations read a pre-agreed envelope format (sentinel tags,
    fenced block, JSON field, ...) and return only the poem content.
    When the envelope is missing or malformed, implementations must
    return the input unchanged so the fallback sanitizer still sees
    the original text.
    """

    @abstractmethod
    def extract(self, text: str) -> str: ...


class IPoemOutputSanitizer(ABC):
    """Cleans raw LLM output so only plain Ukrainian poem lines remain."""

    @abstractmethod
    def sanitize(self, text: str) -> str:
        """Return ``text`` with non-poem lines removed.

        Implementations must be idempotent: ``sanitize(sanitize(x)) == sanitize(x)``.
        Lines that the sanitizer cannot confidently classify as garbage must
        be preserved. If every line is stripped, implementations should
        return the original input unchanged so downstream validators can
        still produce meaningful feedback.
        """
