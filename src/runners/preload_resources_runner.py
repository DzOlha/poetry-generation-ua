"""PreloadResourcesRunner — IRunner wrapper around Stanza + LaBSE preloading.

Replaces the free-function script `scripts/preload_stanza.py`. Keeps logging
consistent across the codebase (structured `ILogger` records instead of raw
`print()`) and lets tests exercise the preload logic via the runner.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from src.composition_root import build_logger
from src.config import AppConfig
from src.domain.ports import ILogger, IRunner, IStressDictionary


@dataclass
class PreloadResourcesRunnerConfig:
    include_stanza: bool = True
    include_labse: bool = True


class PreloadResourcesRunner(IRunner):
    """Downloads the Stanza UA model and LaBSE weights in advance of test runs."""

    def __init__(
        self,
        config: PreloadResourcesRunnerConfig | None = None,
        app_config: AppConfig | None = None,
        logger: ILogger | None = None,
        stress_dictionary: IStressDictionary | None = None,
    ) -> None:
        self._cfg = config or PreloadResourcesRunnerConfig()
        self._app_config = app_config or AppConfig.from_env()
        self._logger = logger or build_logger(self._app_config)
        self._stress_dictionary = stress_dictionary

    def run(self) -> int:
        if self._cfg.include_stanza:
            self._preload_stanza()
        if self._cfg.include_labse:
            self._preload_labse()
        self._logger.info("All resources ready")
        return 0

    # ------------------------------------------------------------------
    # Stanza preloading
    # ------------------------------------------------------------------

    @staticmethod
    def _stanza_dir() -> str:
        return os.environ.get("STANZA_RESOURCES_DIR", os.path.expanduser("~/stanza_resources"))

    def _stanza_model_ready(self) -> bool:
        uk_dir = os.path.join(self._stanza_dir(), "uk")
        if not os.path.isdir(uk_dir):
            return False
        return any(
            any(f.endswith(".pt") for f in files)
            for _, _, files in os.walk(uk_dir)
        )

    def _preload_stanza(self) -> None:
        t0 = time.time()
        stanza_dir = self._stanza_dir()
        if self._stanza_model_ready():
            self._logger.info("Stanza model cached", dir=stanza_dir)
        else:
            self._logger.info("Downloading Stanza UA model", dir=stanza_dir)
            try:
                import stanza

                stanza.download("uk", verbose=True)
            except Exception as exc:
                self._logger.error("Stanza download failed", error=str(exc))
                return
            self._logger.info("Stanza download complete", seconds=round(time.time() - t0, 2))

        self._logger.info("Verifying stress dictionary")
        try:
            if self._stress_dictionary is None:
                self._logger.warning("No stress dictionary injected — skipping verification")
                return
            sd = self._stress_dictionary
            idx = sd.get_stress_index("весна")
            self._logger.info("Stress dictionary OK", stress_index=idx)
        except Exception as exc:
            self._logger.error("Stress dictionary verification failed", error=str(exc))

    # ------------------------------------------------------------------
    # LaBSE preloading
    # ------------------------------------------------------------------

    @staticmethod
    def _labse_model_ready() -> bool:
        hf_cache = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        model_dir = os.path.join(hf_cache, "hub", "models--sentence-transformers--LaBSE")
        return os.path.isdir(model_dir)

    def _preload_labse(self) -> None:
        t0 = time.time()
        if self._labse_model_ready():
            self._logger.info("LaBSE model cached")
            return
        self._logger.info("Downloading LaBSE model")
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("sentence-transformers/LaBSE")
            vec = model.encode(["тест"], normalize_embeddings=True)
            self._logger.info("LaBSE OK", dim=len(vec[0]))
        except Exception as exc:
            self._logger.warning("LaBSE download failed", error=str(exc))
        self._logger.info("LaBSE step finished", seconds=round(time.time() - t0, 2))
