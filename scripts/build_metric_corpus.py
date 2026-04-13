"""Build the auto-detected metric corpus from a local ``data/`` directory.

Thin argparse wrapper around ``BuildMetricCorpusRunner``. Independent from
the theme corpus — both read ``data/`` directly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import AppConfig
from src.infrastructure.corpus.poem_file_parser import PoemFileParser
from src.runners.build_metric_corpus_runner import (
    BuildMetricCorpusRunner,
    BuildMetricCorpusRunnerConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build auto-detected metric corpus from local data/ directory."
    )
    parser.add_argument("--data-dir", type=str, default="data", help="Path to the data directory.")
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path("corpus") / "uk_auto_metric_corpus.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--sample-lines",
        type=int,
        default=None,
        help="Number of leading lines to sample per poem (default: from config).",
    )
    args = parser.parse_args()

    app_config = AppConfig.from_env()

    runner = BuildMetricCorpusRunner(
        config=BuildMetricCorpusRunnerConfig(
            data_dir=args.data_dir,
            out_path=args.out,
            sample_lines=args.sample_lines,
        ),
        parser=PoemFileParser(),
        app_config=app_config,
    )

    sys.exit(runner.run())


if __name__ == "__main__":
    main()
