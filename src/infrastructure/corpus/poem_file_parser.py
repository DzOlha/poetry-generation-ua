"""PoemFileParser — extracts poems from numbered text files.

Extracted from BuildCorpusRunner to separate parsing concerns from
runner orchestration (SRP). The parser owns text normalization, poem
validation heuristics, and the numbered-poem regex grammar.

Implements the ``ICorpusParser`` domain port.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.domain.ports.corpus import ICorpusParser, ParsedPoem


class PoemFileParser(ICorpusParser):
    """Parses numbered-poem text files into structured poem records."""

    @staticmethod
    def normalize_poem_text(text: str) -> str:
        """Normalize whitespace, line endings, and collapse multiple blank lines."""
        t = text.replace("\r\n", "\n").replace("\r", "\n").lower()
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
        return re.sub(r"\n{3,}", "\n\n", t)

    @staticmethod
    def looks_like_poem(
        clean_text: str,
        min_lines: int = 4,
        min_chars: int = 60,
        max_chars: int = 10_000,
    ) -> bool:
        """Heuristic check whether a text block looks like a poem."""
        if not clean_text or len(clean_text) < min_chars or len(clean_text) > max_chars:
            return False
        lines = [ln for ln in clean_text.splitlines() if ln.strip()]
        if len(lines) < min_lines:
            return False
        return bool(re.search(r"[а-яіїєґ]", clean_text))

    def parse_numbered_poems(self, raw_text: str) -> list[ParsedPoem]:
        """Parse numbered poems from a text file in ``N. Title\\nBody`` format."""
        txt = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        header_re = re.compile(r"^\s*(\d+)\.\s*(.*)$", flags=re.MULTILINE)
        matches = list(header_re.finditer(txt))
        if not matches:
            return []

        poems: list[ParsedPoem] = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(txt)
            header_title = (m.group(2) or "").strip() or None
            body = txt[start:end].strip("\n").strip()
            if not body:
                continue

            if header_title is None:
                first_line, *rest = (ln.strip() for ln in body.splitlines() if ln.strip())
                header_title = first_line or None
                body = "\n".join(rest).strip()

            clean = self.normalize_poem_text(body)
            if not self.looks_like_poem(clean):
                continue
            poems.append(ParsedPoem(title=header_title, text=clean))
        return poems

    @staticmethod
    def author_from_path(path: Path, data_dir: Path) -> str | None:
        """Extract author name from the first path component relative to data_dir."""
        try:
            rel = path.relative_to(data_dir)
        except ValueError:
            return None
        return rel.parts[0] if len(rel.parts) >= 2 else None
