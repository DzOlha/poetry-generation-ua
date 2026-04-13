"""Build the RAG-ready poetry corpus from a local `data/` directory.

Thin argparse wrapper around `BuildCorpusRunner`. When the user passes
`--embed`, this script additionally runs `BuildEmbeddingsRunner` so each
runner stays single-purpose — the script, not the runner, owns the
sequencing of "build corpus, then embed it".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import AppConfig
from src.infrastructure.corpus.poem_file_parser import PoemFileParser
from src.runners.build_corpus_runner import BuildCorpusRunner, BuildCorpusRunnerConfig
from src.runners.build_embeddings_runner import (
    BuildEmbeddingsRunner,
    BuildEmbeddingsRunnerConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RAG-ready poetry corpus from local data/ directory (no scraping)."
    )
    parser.add_argument("--data-dir", type=str, default="data", help="Path to the data directory.")
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path("corpus") / "uk_theme_reference_corpus.json"),
        help="Output JSON path.",
    )
    parser.add_argument("--min-count", type=int, default=500, help="Minimum number of poems required.")
    parser.add_argument(
        "--embed",
        action="store_true",
        default=False,
        help="After building the corpus, compute LaBSE embeddings for every poem.",
    )
    args = parser.parse_args()

    app_config = AppConfig.from_env()

    corpus_runner = BuildCorpusRunner(
        config=BuildCorpusRunnerConfig(
            data_dir=args.data_dir,
            out_path=args.out,
            min_count=max(1, int(args.min_count)),
        ),
        parser=PoemFileParser(),
        app_config=app_config,
    )

    exit_code = corpus_runner.run()
    if exit_code != 0 or not args.embed:
        sys.exit(exit_code)

    # Sequencing of "build corpus, then embed" lives in the script so each
    # runner stays single-purpose (see ADR on runner composition).
    embed_runner = BuildEmbeddingsRunner(
        config=BuildEmbeddingsRunnerConfig(corpus_path=args.out),
        app_config=app_config,
    )
    sys.exit(embed_runner.run())


if __name__ == "__main__":
    main()
