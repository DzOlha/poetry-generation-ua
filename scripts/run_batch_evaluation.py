"""Run the full ablation grid: scenarios × ablation configs × seeds.

Thin argparse wrapper that delegates orchestration to BatchEvaluationRunner.
Produces a flat CSV (one row per run) used as input for the contribution
analyzer and the /ablation-report web page.

Run via `python -m scripts.run_batch_evaluation` or after `pip install -e .`.
"""
from __future__ import annotations

import argparse
import sys

from src.config import AppConfig
from src.runners.batch_evaluation_runner import (
    BatchEvaluationRunner,
    BatchEvaluationRunnerConfig,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poetry generation batch-evaluation harness")
    p.add_argument("--seeds", type=int, default=3,
                   help="Number of repetitions per (scenario, config) cell (default: 3)")
    p.add_argument("--category", choices=["normal", "edge", "corner"])
    p.add_argument("--scenario")
    p.add_argument("--config")
    p.add_argument("--corpus-path", default=None, dest="corpus_path")
    p.add_argument("--metric-examples-path", default=None, dest="metric_examples_path")
    p.add_argument("--metric-examples-top-k", type=int, default=2, dest="metric_examples_top_k")
    p.add_argument("--max-iterations", type=int, default=1)
    p.add_argument("--delay", type=float, default=3.0, dest="delay_between_calls_sec",
                   help="Seconds to sleep between LLM calls to avoid rate limits (default: 3.0)")
    p.add_argument("--output", "-o", required=True,
                   help="Output CSV path, e.g. results/batch_<ts>/runs.csv")
    p.add_argument("--resume", action="store_true",
                   help="If --output already exists, keep its successful rows and "
                        "only re-run cells that errored or are missing. Useful when "
                        "the previous batch died on a daily quota error.")
    p.add_argument("--skip-degenerate", action="store_true",
                   help="Skip scenarios marked expected_to_succeed=False "
                        "(C04 unsupported meter, C08 zero feet). They are filtered "
                        "from statistics anyway but still burn LLM quota.")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    app_config = AppConfig.from_env()

    runner_cfg = BatchEvaluationRunnerConfig(
        seeds=args.seeds,
        scenario_id=args.scenario,
        category=args.category,
        config_label=args.config,
        corpus_path=args.corpus_path,
        metric_examples_path=args.metric_examples_path,
        metric_examples_top_k=args.metric_examples_top_k,
        max_iterations=args.max_iterations,
        output_path=args.output,
        delay_between_calls_sec=args.delay_between_calls_sec,
        resume=args.resume,
        skip_degenerate=args.skip_degenerate,
    )

    runner = BatchEvaluationRunner(app_config=app_config, config=runner_cfg)
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
