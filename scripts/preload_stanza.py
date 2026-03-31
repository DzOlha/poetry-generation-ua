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


def _stanza_dir() -> str:
    import os
    return os.environ.get("STANZA_RESOURCES_DIR", os.path.expanduser("~/stanza_resources"))


def _stanza_model_ready() -> bool:
    """Return True if the Ukrainian Stanza model files are already on disk."""
    import os
    uk_dir = os.path.join(_stanza_dir(), "uk")
    if not os.path.isdir(uk_dir):
        return False
    # Any .pt model file means the model was downloaded
    for _, _, files in os.walk(uk_dir):
        if any(f.endswith(".pt") for f in files):
            return True
    return False


def _preload_stanza() -> None:
    t0 = time.time()
    stanza_dir = _stanza_dir()
    if _stanza_model_ready():
        print(f"[preload] Stanza Ukrainian model already cached in {stanza_dir} — skipping download.")
    else:
        print(f"[preload] Downloading Stanza Ukrainian resources to {stanza_dir} …")
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


def _labse_model_ready() -> bool:
    """Return True if the LaBSE model is already in the HuggingFace cache."""
    import os
    hf_cache = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    model_dir = os.path.join(hf_cache, "hub", "models--sentence-transformers--LaBSE")
    return os.path.isdir(model_dir)


def _preload_labse() -> None:
    t0 = time.time()
    if _labse_model_ready():
        print("[preload] LaBSE model already cached — skipping download.")
        return
    print("[preload] Downloading LaBSE sentence-transformer model …")
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
