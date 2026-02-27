from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_CORPUS_PATH = "corpus/uk_poetry_corpus.json"


@dataclass(frozen=True)
class CorpusPoem:
    id: str
    text: str
    author: str | None = None
    approx_theme: list[str] | None = None
    source: str | None = None
    lines: int | None = None
    embedding: list[float] | None = None


def load_corpus_json(path: Path) -> list[CorpusPoem]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    poems: list[CorpusPoem] = []
    for item in raw:
        poems.append(
            CorpusPoem(
                id=str(item.get("id", "")),
                text=str(item.get("text", "")),
                author=item.get("author"),
                approx_theme=item.get("approx_theme"),
                source=item.get("source"),
                lines=item.get("lines"),
                embedding=item.get("embedding"),
            )
        )
    return poems


def corpus_from_env() -> list[CorpusPoem]:
    path = Path(os.getenv("CORPUS_PATH", _DEFAULT_CORPUS_PATH))
    if path.exists():
        return load_corpus_json(path)
    return default_demo_corpus()


def default_demo_corpus() -> list[CorpusPoem]:
    return [
        CorpusPoem(
            id="demo_1",
            author="demo",
            text=(
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            approx_theme=["весна", "ліс"],
            source="demo",
            lines=4,
        ),
        CorpusPoem(
            id="demo_2",
            author="demo",
            text=(
                "У тиші гаю лист тремтить,\n"
                "Немов дихання молоде.\n"
                "Де мох м'який росою спить,\n"
                "Там день прозорий тихо йде.\n"
            ),
            approx_theme=["природа", "тиша"],
            source="demo",
            lines=4,
        ),
    ]
