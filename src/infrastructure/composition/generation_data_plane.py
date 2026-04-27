"""Data-plane composition — repos, embedder, retriever.

Split out from ``generation.py`` so the LLM stack and pipeline-stage
wiring can grow without dragging the data plane along.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.domain.ports import IEmbedder, IMetricRepository, IRetriever, IThemeRepository
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.embeddings import (
    CompositeEmbedder,
    LaBSEEmbedder,
    OfflineDeterministicEmbedder,
)
from src.infrastructure.repositories.metric_repository import JsonMetricRepository
from src.infrastructure.repositories.theme_repository import (
    DemoThemeRepository,
    JsonThemeRepository,
)
from src.infrastructure.retrieval import SemanticRetriever

if TYPE_CHECKING:
    from src.composition_root import Container


class GenerationDataPlaneSubContainer:
    """Theme + metric repositories, embedder, retriever."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def theme_repo(self) -> IThemeRepository:
        def factory() -> IThemeRepository:
            cfg = self._parent.config
            if Path(cfg.corpus_path).exists():
                return JsonThemeRepository(path=cfg.corpus_path)
            return DemoThemeRepository()

        return self._parent._get(CacheKey.THEME_REPO, factory)

    def metric_repo(self) -> IMetricRepository:
        return self._parent._get(
            CacheKey.METRIC_REPO,
            lambda: JsonMetricRepository(
                path=self._parent.config.metric_examples_path,
                meter_canonicalizer=self._parent.primitives.meter_canonicalizer(),
            ),
        )

    def embedder(self) -> IEmbedder:
        def factory() -> IEmbedder:
            cfg = self._parent.config
            offline = OfflineDeterministicEmbedder(logger=self._parent.logger)
            if cfg.offline_embedder:
                return offline
            primary = LaBSEEmbedder(
                logger=self._parent.logger, model_name=cfg.labse_model_name,
            )
            # CompositeEmbedder falls back to the offline embedder on
            # runtime LaBSE failures (model missing, network down, OOM).
            return CompositeEmbedder(
                primary=primary,
                fallback=offline,
                logger=self._parent.logger,
            )

        return self._parent._get(CacheKey.EMBEDDER, factory)

    def retriever(self) -> IRetriever:
        return self._parent._get(
            CacheKey.RETRIEVER,
            lambda: SemanticRetriever(embedder=self.embedder()),
        )
