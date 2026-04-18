"""Sentinel-based poem extractor.

The prompt tells the model to wrap its final poem between sentinel tags
(default: ``<POEM>`` / ``</POEM>``). Everything before the opening tag is
chain-of-thought; everything after the closing tag is epilogue. Both are
discarded.

Extraction is tolerant of realistic model failures:

* Missing tags → return input unchanged (fallback sanitizer handles it).
* Multiple ``<POEM>...</POEM>`` blocks → use the **last** complete one,
  which is the pattern when a model revises itself during CoT.
* Opening tag without a matching close → take text after the last open.
* Empty block (``<POEM></POEM>``) → treat as missing; return input.

The comparison is case-insensitive so ``<poem>`` / ``<Poem>`` also work.
"""
from __future__ import annotations

import re

from src.domain.ports import IPoemExtractor


class SentinelPoemExtractor(IPoemExtractor):
    """Pulls the poem block out of ``<POEM>...</POEM>`` sentinels."""

    DEFAULT_OPEN = "<POEM>"
    DEFAULT_CLOSE = "</POEM>"

    def __init__(self, open_tag: str = DEFAULT_OPEN, close_tag: str = DEFAULT_CLOSE) -> None:
        if not open_tag or not close_tag:
            raise ValueError("open_tag and close_tag must be non-empty")
        self._open = open_tag
        self._close = close_tag
        self._paired_re = re.compile(
            re.escape(open_tag) + r"(.*?)" + re.escape(close_tag),
            flags=re.DOTALL | re.IGNORECASE,
        )
        self._open_re = re.compile(re.escape(open_tag), flags=re.IGNORECASE)

    def extract(self, text: str) -> str:
        if not text:
            return text

        paired = self._paired_re.findall(text)
        if paired:
            # Take the LAST paired block — models often revise mid-CoT,
            # and the last block is the one they committed to.
            block = paired[-1].strip()
            if block:
                return block + "\n"
            return text

        # Opening tag present but no close — salvage everything after the
        # last open tag. This is the common mode when the model runs out
        # of output tokens partway through the final poem.
        open_matches = list(self._open_re.finditer(text))
        if open_matches:
            tail = text[open_matches[-1].end():].strip()
            if tail:
                return tail + "\n"

        return text
