"""Pre-download heavy ML resources required by the test suite.

Downloads:
  1. Stanza Ukrainian model  (~500 MB)  — used by ukrainian-word-stress / StressDict
  2. LaBSE sentence-transformer (~1.8 GB) — used by SemanticRetriever

Run this script once before tests.  Results are cached in Docker
volumes so subsequent runs finish instantly.
"""
from __future__ import annotations

import sys
import time


def _preload_stanza() -> None:
    print("[preload] Downloading Stanza Ukrainian resources …")
    t0 = time.time()
    try:
        import stanza
        stanza.download("uk", verbose=True)
    except Exception as exc:
        print(f"[preload] stanza.download failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[preload] Stanza download finished in {time.time() - t0:.1f}s")

    print("[preload] Verifying StressDict initialisation …")
    try:
        sys.path.insert(0, ".")
        from src.meter.stress import StressDict

        sd = StressDict(on_ambiguity="first")
        idx = sd.get_stress_index("весна")
        print(f"[preload] StressDict OK  (stress index for 'весна' = {idx})")
    except Exception as exc:
        print(f"[preload] StressDict verification failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _preload_labse() -> None:
    print("[preload] Downloading LaBSE sentence-transformer model …")
    t0 = time.time()
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/LaBSE")
        vec = model.encode(["тест"], normalize_embeddings=True)
        print(f"[preload] LaBSE OK  (vector dim = {len(vec[0])})")
    except Exception as exc:
        print(f"[preload] LaBSE download failed: {exc}", file=sys.stderr)
        print("[preload] SemanticRetriever will use random-vector fallback.")
    print(f"[preload] LaBSE step finished in {time.time() - t0:.1f}s")


def main() -> None:
    _preload_stanza()
    _preload_labse()
    print("[preload] All resources ready. Starting tests.")


if __name__ == "__main__":
    main()
