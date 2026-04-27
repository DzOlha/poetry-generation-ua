"""Tests for LaBSEEmbedder error-handling without touching the network.

The real model (~1.8 GB) lives behind sentence_transformers; we never want
unit tests to download it. These tests use monkey-patching to inject a
fake SentenceTransformer that exercises the same error-wrapping branches
(`EmbedderError` on load failure, `EmbedderError` on encode failure)
that production hits.

The "happy path with real model" lives separately as a `component`-marked
test, opt-in via `make test-component`.
"""
from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.domain.errors import EmbedderError
from src.infrastructure.embeddings.labse import LaBSEEmbedder
from src.infrastructure.logging import NullLogger


def _install_fake_st(monkeypatch, factory) -> None:  # noqa: ANN001
    """Stub `sentence_transformers.SentenceTransformer` for one test.

    The real package may or may not be installed in the test environment;
    we override its module entry so `from sentence_transformers import
    SentenceTransformer` inside `_load()` returns our factory.
    """
    fake = ModuleType("sentence_transformers")
    fake.SentenceTransformer = factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)


class TestLazyLoad:
    def test_load_failure_wrapped_as_embedder_error(self, monkeypatch) -> None:  # noqa: ANN001
        def _failing_factory(name: str):  # noqa: ANN202
            raise OSError(f"cannot reach huggingface for {name}")

        _install_fake_st(monkeypatch, _failing_factory)
        emb = LaBSEEmbedder(logger=NullLogger())
        with pytest.raises(EmbedderError) as exc_info:
            emb.encode("привіт")
        assert "LaBSE model" in str(exc_info.value)
        assert "unavailable" in str(exc_info.value)

    def test_model_loaded_only_once(self, monkeypatch) -> None:  # noqa: ANN001
        load_calls = {"n": 0}

        def _factory(name: str):  # noqa: ANN202
            load_calls["n"] += 1
            return SimpleNamespace(
                encode=lambda texts, normalize_embeddings: [[0.5, 0.5]],
            )

        _install_fake_st(monkeypatch, _factory)
        emb = LaBSEEmbedder(logger=NullLogger())
        emb.encode("один")
        emb.encode("два")
        emb.encode("три")
        assert load_calls["n"] == 1, "Model should be cached after first load"


class TestEncode:
    def test_encode_returns_floats_from_model(self, monkeypatch) -> None:  # noqa: ANN001
        def _factory(name: str):  # noqa: ANN202
            return SimpleNamespace(
                encode=lambda texts, normalize_embeddings: [[0.1, 0.2, 0.3]],
            )

        _install_fake_st(monkeypatch, _factory)
        emb = LaBSEEmbedder(logger=NullLogger())
        out = emb.encode("текст")
        assert out == pytest.approx([0.1, 0.2, 0.3])
        assert all(isinstance(x, float) for x in out)

    def test_encode_failure_wrapped_as_embedder_error(self, monkeypatch) -> None:  # noqa: ANN001
        def _failing_encode(texts, normalize_embeddings):  # noqa: ANN001, ANN202
            raise RuntimeError("CUDA OOM")

        def _factory(name: str):  # noqa: ANN202
            return SimpleNamespace(encode=_failing_encode)

        _install_fake_st(monkeypatch, _factory)
        emb = LaBSEEmbedder(logger=NullLogger())
        with pytest.raises(EmbedderError) as exc_info:
            emb.encode("щось")
        assert "encode failed" in str(exc_info.value)
        assert "CUDA OOM" in str(exc_info.value)

    def test_embedder_error_passthrough_not_double_wrapped(self, monkeypatch) -> None:  # noqa: ANN001
        # If `_load` itself raises an EmbedderError, the encode() except
        # branch must let it propagate as-is rather than re-wrap with
        # "encode failed" prefix — that would lose the original message.
        def _factory(name: str):  # noqa: ANN202
            raise OSError("network down")  # _load wraps this as EmbedderError

        _install_fake_st(monkeypatch, _factory)
        emb = LaBSEEmbedder(logger=NullLogger())
        with pytest.raises(EmbedderError) as exc_info:
            emb.encode("a")
        # Message should be the load-failure phrasing, not "encode failed".
        assert "unavailable" in str(exc_info.value)
        assert "encode failed" not in str(exc_info.value)
