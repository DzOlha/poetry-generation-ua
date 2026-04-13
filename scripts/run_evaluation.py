"""Run the full evaluation matrix: scenarios × ablation configs.

Thin argparse wrapper that delegates all orchestration to EvaluationRunner.
Run via `python -m scripts.run_evaluation` or after `pip install -e .`.
"""
from __future__ import annotations

import argparse
import sys

from src.config import AppConfig
from src.runners.evaluation_runner import EvaluationRunner, EvaluationRunnerConfig


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poetry generation evaluation harness")
    p.add_argument("--category", choices=["normal", "edge", "corner"])
    p.add_argument("--scenario")
    p.add_argument("--config")
    p.add_argument("--corpus-path", default=None, dest="corpus_path")
    p.add_argument("--metric-examples-path", default=None, dest="metric_examples_path")
    p.add_argument("--metric-examples-top-k", type=int, default=2, dest="metric_examples_top_k")
    p.add_argument("--max-iterations", type=int, default=1)
    p.add_argument("--stanzas", type=int, default=None)
    p.add_argument("--lines-per-stanza", type=int, default=None, dest="lines_per_stanza")
    p.add_argument("--output", "-o")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    app_config = AppConfig.from_env()

    runner_cfg = EvaluationRunnerConfig(
        scenario_id=args.scenario,
        category=args.category,
        config_label=args.config,
        corpus_path=args.corpus_path,  # None falls back to app_config.corpus_path
        metric_examples_path=args.metric_examples_path,
        metric_examples_top_k=args.metric_examples_top_k,
        max_iterations=args.max_iterations,
        stanzas=args.stanzas,
        lines_per_stanza=args.lines_per_stanza,
        output_path=args.output,
        verbose=args.verbose,
    )

    runner = EvaluationRunner(app_config=app_config, config=runner_cfg)
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
