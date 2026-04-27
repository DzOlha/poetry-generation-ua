"""BuildEmbeddingsRunner — IRunner that pre-computes LaBSE embeddings.

Replaces the free-function script `scripts/build_corpus_embeddings.py`.
The runner logs progress via `ILogger` and surfaces import errors as
`DomainError` subclasses so callers see structured failures.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.composition_root import build_logger
from src.config import AppConfig
from src.domain.errors import DomainError, EmbedderError
from src.domain.models.corpus_entry import CorpusEntry
from src.domain.ports import ILogger, IRunner


@dataclass
class BuildEmbeddingsRunnerConfig:
    corpus_path: str | None = None  # falls back to AppConfig.corpus_path
    batch_size: int = 32


class BuildEmbeddingsRunner(IRunner):
    """Encodes every poem in the corpus with LaBSE and writes the vectors back."""

    def __init__(
        self,
        config: BuildEmbeddingsRunnerConfig,
        app_config: AppConfig | None = None,
        logger: ILogger | None = None,
    ) -> None:
        self._cfg = config
        self._app_config = app_config or AppConfig.from_env()
        self._logger = logger or build_logger(self._app_config)

    def run(self) -> int:
        corpus_path = Path(self._cfg.corpus_path) if self._cfg.corpus_path else self._app_config.corpus_path
        try:
            self._build_embeddings(corpus_path)
        except DomainError as exc:
            self._logger.error("Embedding build failed", error=str(exc))
            return 1
        return 0

    def _build_embeddings(self, corpus_path: Path) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbedderError(
                "sentence-transformers is not installed — install it or use the offline embedder",
            ) from exc

        self._logger.info("Loading corpus", path=str(corpus_path))
        poems: list[CorpusEntry] = json.loads(corpus_path.read_text(encoding="utf-8"))

        already = sum(1 for p in poems if p.get("embedding"))
        self._logger.info("Corpus loaded", total=len(poems), already_embedded=already)

        texts_to_encode = [(i, p) for i, p in enumerate(poems) if not p.get("embedding")]
        if not texts_to_encode:
            self._logger.info("All poems already embedded — nothing to do")
            return

        self._logger.info("Loading LaBSE model", model=self._app_config.labse_model_name)
        model = SentenceTransformer(self._app_config.labse_model_name)

        indices = [i for i, _ in texts_to_encode]
        texts = [p["text"] for _, p in texts_to_encode]

        self._logger.info(
            "Encoding poems",
            count=len(texts),
            batch_size=self._cfg.batch_size,
        )
        vectors = model.encode(
            texts,
            batch_size=self._cfg.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        for idx, vec in zip(indices, vectors):
            poems[idx]["embedding"] = [round(float(x), 6) for x in vec]

        corpus_path.write_text(
            json.dumps(poems, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._logger.info("Embeddings written", count=len(texts), path=str(corpus_path))
