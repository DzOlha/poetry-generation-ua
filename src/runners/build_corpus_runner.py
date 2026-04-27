"""BuildCorpusRunner — IRunner that turns a local `data/` directory into a
JSON corpus ready for retrieval.

Single-responsibility runner: it builds the corpus JSON file and stops.
Embedding is a separate concern handled by `BuildEmbeddingsRunner`;
`scripts/build_corpus_from_data_dir.py` chains the two runners when the
user passes `--embed` so each runner stays single-purpose.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from src.composition_root import build_logger
from src.config import AppConfig
from src.domain.errors import DomainError, RepositoryError
from src.domain.models.corpus_entry import CorpusEntry
from src.domain.ports import ICorpusParser, ILogger, IRunner


@dataclass
class BuildCorpusRunnerConfig:
    data_dir: str = "data"
    out_path: str = "corpus/uk_theme_reference_corpus.json"
    min_count: int = 500


class BuildCorpusRunner(IRunner):
    """Scans the data directory and emits a JSON corpus file."""

    def __init__(
        self,
        config: BuildCorpusRunnerConfig,
        parser: ICorpusParser,
        app_config: AppConfig | None = None,
        logger: ILogger | None = None,
    ) -> None:
        self._cfg = config
        self._app_config = app_config or AppConfig.from_env()
        self._logger = logger or build_logger(self._app_config)
        self._parser = parser

    def run(self) -> int:
        cfg = self._cfg
        data_dir = Path(cfg.data_dir)
        out_path = Path(cfg.out_path)
        try:
            poems = self._build_corpus(data_dir, out_path, cfg.min_count)
        except DomainError as exc:
            self._logger.error("Corpus build failed", error=str(exc))
            return 1

        self._logger.info("Corpus built", poems=len(poems), out=str(out_path))
        return 0

    def _build_corpus(
        self,
        data_dir: Path,
        out_path: Path,
        min_count: int,
    ) -> list[CorpusEntry]:
        files = sorted([p for p in data_dir.rglob("*.txt") if p.is_file()])
        if not files:
            raise RepositoryError(f"No .txt files found under: {data_dir}")

        poems_out: list[CorpusEntry] = []
        seen_hashes: set[str] = set()

        for f in files:
            raw = f.read_text(encoding="utf-8", errors="replace")
            parsed = self._parser.parse_numbered_poems(raw)
            author = self._parser.author_from_path(f, data_dir)

            for idx, poem in enumerate(parsed, start=1):
                h = hashlib.sha256(poem.text.encode("utf-8")).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)

                lines_count = len([ln for ln in poem.text.splitlines() if ln.strip()])
                poems_out.append({
                    "id": f"local_{author or 'unknown'}_{f.stem}_{idx}",
                    "text": poem.text,
                    "author": author,
                    "approx_theme": [],
                    "source": "local_data",
                    "lines": lines_count,
                    "title": poem.title,
                    "path": str(f),
                })

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(poems_out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if len(poems_out) < min_count:
            raise RepositoryError(
                f"Only found {len(poems_out)} poems under {data_dir}, "
                f"expected at least {min_count}.",
            )
        return poems_out
