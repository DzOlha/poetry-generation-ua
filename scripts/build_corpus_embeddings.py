"""Pre-compute LaBSE embeddings for every poem in the corpus JSON and write
them back into the file so that SemanticRetriever can skip on-the-fly encoding.

Usage:
    python scripts/build_corpus_embeddings.py
    python scripts/build_corpus_embeddings.py --corpus corpus/uk_poetry_corpus.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_embeddings(corpus_path: Path) -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        )

    print(f"Loading corpus from {corpus_path} ...")
    poems: list[dict] = json.loads(corpus_path.read_text(encoding="utf-8"))

    already = sum(1 for p in poems if p.get("embedding"))
    print(f"  {len(poems)} poems total, {already} already have embeddings.")

    texts_to_encode = [(i, p) for i, p in enumerate(poems) if not p.get("embedding")]
    if not texts_to_encode:
        print("All poems already have embeddings. Nothing to do.")
        return

    print(f"Loading LaBSE model (sentence-transformers/LaBSE) ...")
    model = SentenceTransformer("sentence-transformers/LaBSE")

    batch_size = 32
    indices = [i for i, _ in texts_to_encode]
    texts   = [p["text"] for _, p in texts_to_encode]

    print(f"Encoding {len(texts)} poems in batches of {batch_size} ...")
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    for idx, vec in zip(indices, vectors):
        poems[idx]["embedding"] = [round(float(x), 6) for x in vec]

    corpus_path.write_text(
        json.dumps(poems, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Done. Wrote embeddings for {len(texts)} poems to {corpus_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-compute LaBSE embeddings for corpus poems.")
    parser.add_argument(
        "--corpus",
        default="corpus/uk_poetry_corpus.json",
        help="Path to the corpus JSON file (default: corpus/uk_poetry_corpus.json)",
    )
    args = parser.parse_args()
    build_embeddings(Path(args.corpus))


if __name__ == "__main__":
    main()
