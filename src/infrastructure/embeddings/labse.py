"""LaBSE semantic embedder — multilingual sentence embedding adapter.

Unlike the previous implementation, LaBSEEmbedder no longer silently falls
back to a deterministic random vector. Silent fallback masked network/disk
failures during evaluation, making the whole retrieval metric meaningless.

If the caller wants offline behaviour, they must explicitly use
OfflineDeterministicEmbedder instead. Production wiring picks LaBSE; test
fixtures pick the offline embedder.

LaBSEEmbedder raises EmbedderError on any failure; it never returns garbage.
"""
from __future__ import annotations

import math
import random
from typing import Any

from src.domain.errors import EmbedderError
from src.domain.ports import IEmbedder, ILogger


class LaBSEEmbedder(IEmbedder):
    """Encodes text using the multilingual LaBSE model (sentence-transformers).

    Args:
        logger: ILogger used to warn about lazy-load or encode failures.
        model_name: SentenceTransformer model identifier.
    """

    def __init__(
        self,
        logger: ILogger,
        model_name: str = "sentence-transformers/LaBSE",
    ) -> None:
        self._model_name = model_name
        self._model: object | None = None
        self._logger: ILogger = logger

    def encode(self, text: str) -> list[float]:
        try:
            model = self._load()
            vec = model.encode([text], normalize_embeddings=True)[0]
            return [float(x) for x in vec]
        except EmbedderError:
            raise
        except Exception as exc:
            self._logger.error(
                "LaBSE encode failed",
                model=self._model_name,
                error=str(exc),
            )
            raise EmbedderError(f"LaBSE encode failed: {exc}") from exc

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except Exception as exc:
                self._logger.error(
                    "LaBSE model load failed",
                    model=self._model_name,
                    error=str(exc),
                )
                raise EmbedderError(
                    f"LaBSE model {self._model_name!r} unavailable: {exc}"
                ) from exc
        return self._model


class OfflineDeterministicEmbedder(IEmbedder):
    """Deterministic pseudo-random embedder for offline development and tests.

    Produces a stable unit vector for each input string, derived from a hash.
    Use this when the production embedder cannot be loaded (CI with no
    network, local dev without the ML stack, unit tests).

    The "retrieval is not meaningful" warning is emitted lazily on the first
    encode() call rather than in __init__ so construction stays side-effect-free.
    """

    def __init__(self, logger: ILogger, dim: int = 768) -> None:
        self._dim = dim
        self._logger: ILogger = logger
        self._warned_about_quality: bool = False

    def encode(self, text: str) -> list[float]:
        if not self._warned_about_quality:
            self._logger.info(
                "Using OfflineDeterministicEmbedder — retrieval metrics are not meaningful",
            )
            self._warned_about_quality = True
        rng = random.Random(abs(hash(text)) % (2 ** 32))
        vec = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec
