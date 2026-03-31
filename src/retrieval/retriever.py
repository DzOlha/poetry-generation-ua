from __future__ import annotations

import math
import random
from dataclasses import dataclass

from src.retrieval.corpus import CorpusPoem


@dataclass(frozen=True)
class RetrievalItem:
    poem_id: str
    text: str
    similarity: float


class SemanticRetriever:
    def __init__(self, model_name: str = "sentence-transformers/LaBSE") -> None:
        self.model_name = model_name
        self._model = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        except Exception:
            self._model = None

    def encode(self, text: str) -> list[float]:
        self._load_model()
        if self._model is None:
            rng = random.Random(abs(hash(text)) % (2**32))
            return [rng.gauss(0.0, 1.0) for _ in range(256)]

        vec = self._model.encode([text], normalize_embeddings=True)
        out = vec[0]
        return [float(x) for x in out]

    def retrieve(self, theme_description: str, corpus: list[CorpusPoem], top_k: int = 5) -> list[RetrievalItem]:
        theme_vec = self.encode(theme_description)
        items: list[tuple[float, CorpusPoem]] = []

        for poem in corpus:
            if poem.embedding is not None:
                p_vec = [float(x) for x in poem.embedding]
            else:
                p_vec = self.encode(poem.text)

            dot = sum(a * b for a, b in zip(theme_vec, p_vec))
            norm_a = math.sqrt(sum(a * a for a in theme_vec))
            norm_b = math.sqrt(sum(b * b for b in p_vec))
            denom = norm_a * norm_b
            sim = float(dot / denom) if denom else 0.0
            items.append((sim, poem))

        items.sort(key=lambda x: x[0], reverse=True)
        top = items[: max(1, top_k)]
        return [RetrievalItem(poem_id=p.id, text=p.text, similarity=sim) for sim, p in top]


def build_rag_prompt(
    theme: str,
    meter: str,
    rhyme_scheme: str,
    retrieved: list[RetrievalItem],
    stanza_count: int = 1,
    lines_per_stanza: int = 4,
    metric_examples: list | None = None,
) -> str:
    excerpts = "\n".join(item.text.strip() for item in retrieved)
    total_lines = stanza_count * lines_per_stanza
    structure = (
        f"{stanza_count} stanza{'s' if stanza_count > 1 else ''} "
        f"of {lines_per_stanza} lines each ({total_lines} lines total)"
    )

    metric_section = ""
    if metric_examples:
        examples_text = "\n\n".join(e.text.strip() for e in metric_examples)
        metric_section = (
            f"\nUse these verified examples as METER and RHYME reference "
            f"(they demonstrate {meter} meter with {rhyme_scheme} rhyme scheme"
            f" — follow this rhythm and rhyme pattern exactly):\n"
            f"{examples_text}\n"
        )

    return (
        "Use the following poetic excerpts as thematic inspiration (do not copy):\n"
        f"{excerpts}\n"
        f"{metric_section}\n"
        f"Theme: {theme}\n"
        f"Meter: {meter}\n"
        f"Rhyme scheme: {rhyme_scheme}\n"
        f"Structure: {structure}\n"
        f"Generate a Ukrainian poem with exactly {total_lines} lines."
    )
