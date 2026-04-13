"""Typed dictionary describing a single poem in the corpus JSON.

Used by runners and repositories that read/write the corpus JSON
directly, replacing untyped ``dict[str, Any]`` for better static
analysis and IDE support.
"""
from __future__ import annotations

from typing import TypedDict


class CorpusEntry(TypedDict, total=False):
    """Shape of one element in the corpus JSON array.

    ``id``, ``text``, and ``lines`` are always present for valid entries.
    The remaining fields are optional (some poems lack author metadata
    or pre-computed embeddings).
    """

    id: str
    text: str
    author: str | None
    approx_theme: list[str]
    source: str | None
    lines: int
    title: str | None
    path: str | None
    embedding: list[float] | None
