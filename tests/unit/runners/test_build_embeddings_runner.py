"""Unit tests for BuildEmbeddingsRunner."""
from __future__ import annotations

import json
from pathlib import Path

from src.infrastructure.logging import CollectingLogger
from src.runners.build_embeddings_runner import (
    BuildEmbeddingsRunner,
    BuildEmbeddingsRunnerConfig,
)


class TestBuildEmbeddingsRunner:
    def test_all_already_embedded_is_noop(self, tmp_path: Path) -> None:
        corpus_path = tmp_path / "corpus.json"
        corpus_path.write_text(
            json.dumps([{"text": "вірш", "embedding": [0.1, 0.2]}]),
            encoding="utf-8",
        )
        logger = CollectingLogger()
        cfg = BuildEmbeddingsRunnerConfig(corpus_path=str(corpus_path))
        runner = BuildEmbeddingsRunner(config=cfg, logger=logger)
        code = runner.run()
        assert code == 0
        messages = [r[1] for r in logger.records]
        assert any("already embedded" in m for m in messages)

    def test_empty_corpus_is_noop(self, tmp_path: Path) -> None:
        corpus_path = tmp_path / "corpus.json"
        corpus_path.write_text(json.dumps([]), encoding="utf-8")
        logger = CollectingLogger()
        cfg = BuildEmbeddingsRunnerConfig(corpus_path=str(corpus_path))
        runner = BuildEmbeddingsRunner(config=cfg, logger=logger)
        code = runner.run()
        assert code == 0
