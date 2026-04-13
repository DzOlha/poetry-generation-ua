"""Typed dictionary describing a single poem in the auto-detected metric corpus.

Mirrors the shape of ``uk_metric-rhyme_reference_corpus.json`` but adds
accuracy fields and marks entries as ``verified: false`` (auto-detected).
"""
from __future__ import annotations

from typing import TypedDict


class MetricCorpusEntry(TypedDict, total=False):
    """Shape of one element in the auto-detected metric corpus JSON array."""

    id: str
    meter: str
    feet: int
    scheme: str
    meter_accuracy: float
    rhyme_accuracy: float
    verified: bool
    source: str
    author: str | None
    title: str | None
    text: str
