"""Pre-compute LaBSE embeddings for every poem in the corpus JSON.

Thin argparse wrapper around `BuildEmbeddingsRunner`.
"""
from __future__ import annotations

import argparse
import sys

from src.config import AppConfig
from src.runners.build_embeddings_runner import (
    BuildEmbeddingsRunner,
    BuildEmbeddingsRunnerConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-compute LaBSE embeddings for corpus poems.")
    parser.add_argument(
        "--corpus",
        default=None,
        help="Path to the corpus JSON file (default: AppConfig.corpus_path).",
    )
    args = parser.parse_args()

    runner = BuildEmbeddingsRunner(
        config=BuildEmbeddingsRunnerConfig(corpus_path=args.corpus),
        app_config=AppConfig.from_env(),
    )
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
