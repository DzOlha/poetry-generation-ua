import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.baseline import run_baseline
from src.pipeline.full_system import run_full_pipeline

if __name__ == "__main__":
    run_baseline(theme="весна у лісі", meter="ямб")

    poem, report = run_full_pipeline(
        theme="весна у лісі",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        max_iterations=3,
        top_k=3,
    )
    print("\n=== GENERATED POEM ===\n")
    print(poem)
    print("\n=== REPORT ===\n")
    print(report)
