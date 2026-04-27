"""Component test: real LaBSE model load + encode.

Marked `component` — opt-in via `make test-component`. Requires:
  * network access for the first run (~1.8 GB download into HF cache);
  * `sentence_transformers` installed.

Default `make test` / `make test-unit` skip this entirely. CI never runs
it. Use locally to verify the production embedder still wires up before
shipping a release.
"""
from __future__ import annotations

import math

import pytest

from src.infrastructure.embeddings.labse import LaBSEEmbedder
from src.infrastructure.logging import NullLogger

pytestmark = pytest.mark.component


def test_labse_encodes_ukrainian_text_to_unit_vector() -> None:
    pytest.importorskip("sentence_transformers")

    embedder = LaBSEEmbedder(logger=NullLogger())
    vec = embedder.encode("весна у лісі, пробудження природи")

    assert isinstance(vec, list)
    assert all(isinstance(x, float) for x in vec)
    assert len(vec) == 768  # canonical LaBSE dimensionality
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-3, f"normalize_embeddings=True should yield unit vector, got |v|={norm}"


def test_labse_thematically_similar_phrases_score_close() -> None:
    pytest.importorskip("sentence_transformers")

    embedder = LaBSEEmbedder(logger=NullLogger())
    a = embedder.encode("осінь у лісі")
    b = embedder.encode("осіння природа")
    c = embedder.encode("компʼютерний процесор")

    def cos(u: list[float], v: list[float]) -> float:
        return sum(x * y for x, y in zip(u, v, strict=True))

    sim_ab = cos(a, b)
    sim_ac = cos(a, c)
    # Thematic neighbours should score higher than off-topic — sanity
    # check that LaBSE actually loaded (and not some random tensor).
    assert sim_ab > sim_ac
