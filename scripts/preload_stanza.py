"""Pre-download heavy ML resources required by the test suite.

Thin argparse wrapper around `PreloadResourcesRunner`. Kept under the
original filename for backwards compatibility with the Docker entrypoint.
"""
from __future__ import annotations

import sys

from src.runners.preload_resources_runner import (
    PreloadResourcesRunner,
    PreloadResourcesRunnerConfig,
)


def main() -> None:
    runner = PreloadResourcesRunner(config=PreloadResourcesRunnerConfig())
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
