"""Thin argparse wrapper around GenerateRunner for ad-hoc poem generation."""
from __future__ import annotations

import argparse
import sys

from src.config import AppConfig
from src.runners.generate_runner import GenerateRunner, GenerateRunnerConfig


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a Ukrainian poem via the full pipeline")
    p.add_argument("--theme", default="весна у лісі")
    p.add_argument("--meter", default="ямб")
    p.add_argument("--feet", type=int, default=4)
    p.add_argument("--scheme", default="ABAB")
    p.add_argument("--stanzas", type=int, default=2)
    p.add_argument("--lines", type=int, default=4)
    p.add_argument("--iterations", type=int, default=3)
    p.add_argument("--top-k", type=int, default=5, dest="top_k")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    runner_cfg = GenerateRunnerConfig(
        theme=args.theme,
        meter=args.meter,
        feet=args.feet,
        scheme=args.scheme,
        stanzas=args.stanzas,
        lines_per_stanza=args.lines,
        iterations=args.iterations,
        top_k=args.top_k,
    )
    runner = GenerateRunner(app_config=AppConfig.from_env(), config=runner_cfg)
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
