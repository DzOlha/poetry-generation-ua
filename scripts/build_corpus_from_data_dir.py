from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedPoem:
    title: str | None
    text: str


def normalize_poem_text(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = t.lower()

    lines = [re.sub(r"\s+", " ", ln).strip() for ln in t.split("\n")]

    out_lines: list[str] = []
    blank = 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 1:
                out_lines.append("")
            continue
        blank = 0
        out_lines.append(ln)

    t = "\n".join(out_lines).strip()
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def looks_like_poem(clean_text: str, min_lines: int = 4, min_chars: int = 60, max_chars: int = 10000) -> bool:
    if not clean_text:
        return False
    if len(clean_text) < min_chars or len(clean_text) > max_chars:
        return False
    lines = [ln for ln in clean_text.splitlines() if ln.strip()]
    if len(lines) < min_lines:
        return False
    if not re.search(r"[а-яіїєґ]", clean_text):
        return False
    return True


def parse_numbered_poems(raw_text: str) -> list[ParsedPoem]:
    """Parse files like:

    1. Title
    line...

    2. Another title
    ...

    If a poem has no clear title line, the first non-empty line after marker is used.
    """
    txt = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # Find headers like "12. ..." at line start
    header_re = re.compile(r"^\s*(\d+)\.\s*(.*)$", flags=re.MULTILINE)
    matches = list(header_re.finditer(txt))
    if not matches:
        return []

    poems: list[ParsedPoem] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(txt)

        header_title = (m.group(2) or "").strip() or None
        body = txt[start:end].strip("\n")
        body = body.strip()

        if not body:
            continue

        # Some sources store title in header and start body immediately. Keep as is.
        # Also handle case where header is only number and title is actually first line.
        if header_title is None:
            first_line, *rest = [ln.strip() for ln in body.splitlines() if ln.strip()]
            header_title = first_line if first_line else None
            body = "\n".join(rest).strip()

        clean = normalize_poem_text(body)
        if not looks_like_poem(clean):
            continue

        poems.append(ParsedPoem(title=header_title, text=clean))

    return poems


def author_from_path(path: Path, data_dir: Path) -> str | None:
    try:
        rel = path.relative_to(data_dir)
    except Exception:
        return None

    if len(rel.parts) >= 2:
        # data/<author>/<file>.txt
        return rel.parts[0]
    return None


def build_corpus(data_dir: Path, out_path: Path, min_count: int = 500) -> list[dict]:
    files = sorted([p for p in data_dir.rglob("*.txt") if p.is_file()])
    if not files:
        raise SystemExit(f"No .txt files found under: {data_dir}")

    poems_out: list[dict] = []
    seen_hashes: set[str] = set()

    for f in files:
        raw = f.read_text(encoding="utf-8", errors="replace")
        parsed = parse_numbered_poems(raw)
        author = author_from_path(f, data_dir)

        for idx, poem in enumerate(parsed, start=1):
            h = str(hash(poem.text))
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            lines_count = len([ln for ln in poem.text.splitlines() if ln.strip()])
            poems_out.append(
                {
                    "id": f"local_{author or 'unknown'}_{f.stem}_{idx}",
                    "text": poem.text,
                    "author": author,
                    "approx_theme": [],
                    "source": "local_data",
                    "lines": lines_count,
                    "title": poem.title,
                    "path": str(f),
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(poems_out, ensure_ascii=False, indent=2), encoding="utf-8")

    if len(poems_out) < min_count:
        raise SystemExit(
            f"Only found {len(poems_out)} poems under {data_dir}, expected at least {min_count}. "
            "Add more source files to data/ or lower --min-count."
        )

    return poems_out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RAG-ready poetry corpus from local data/ directory (no scraping)."
    )
    parser.add_argument("--data-dir", type=str, default="data", help="Path to the data directory.")
    parser.add_argument("--out", type=str, default=str(Path("corpus") / "uk_poetry_corpus.json"),
                        help="Output JSON path.")
    parser.add_argument("--min-count", type=int, default=500, help="Minimum number of poems required.")
    parser.add_argument(
        "--embed",
        action="store_true",
        default=False,
        help="After building the corpus, compute LaBSE embeddings for every poem and write them back.",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_path = Path(args.out)

    poems = build_corpus(data_dir=data_dir, out_path=out_path, min_count=max(1, int(args.min_count)))
    print(f"Saved {len(poems)} poems to {out_path}")

    if args.embed:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.build_corpus_embeddings import build_embeddings
        build_embeddings(out_path)


if __name__ == "__main__":
    main()
