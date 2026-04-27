"""Unit tests for ``PoemFileParser``.

Covers normalisation, heuristic poem detection, and the numbered-poem
grammar — the three responsibilities the audit flagged as missing test
coverage in ``src/infrastructure/corpus/``.
"""
from __future__ import annotations

from pathlib import Path

from src.infrastructure.corpus import PoemFileParser

# ---------------------------------------------------------------------------
# normalize_poem_text
# ---------------------------------------------------------------------------

class TestNormalizePoemText:
    def test_lowercases_text(self) -> None:
        result = PoemFileParser.normalize_poem_text("ВЕСНА В ЛІСІ")
        assert result == "весна в лісі"

    def test_collapses_horizontal_whitespace(self) -> None:
        result = PoemFileParser.normalize_poem_text("слово  одне\tдва")
        assert result == "слово одне два"

    def test_normalizes_crlf_and_cr(self) -> None:
        result = PoemFileParser.normalize_poem_text("рядок\r\nдва\rтри")
        # Three CR/CRLF terminated lines flatten into three lines.
        assert result == "рядок\nдва\nтри"

    def test_collapses_three_or_more_blank_lines(self) -> None:
        text = "перший\n\n\n\nдругий"
        result = PoemFileParser.normalize_poem_text(text)
        assert result == "перший\n\nдругий"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        result = PoemFileParser.normalize_poem_text("\n\n  весна  \n\n")
        assert result == "весна"


# ---------------------------------------------------------------------------
# looks_like_poem
# ---------------------------------------------------------------------------

class TestLooksLikePoem:
    def _long_ukrainian_block(self, lines: int = 4) -> str:
        body = "\n".join(["слово слово слово слово слово слово"] * lines)
        # Pad to >= 60 chars even on lower line counts.
        return body.ljust(60, "а")

    def test_accepts_typical_ukrainian_poem(self) -> None:
        assert PoemFileParser.looks_like_poem(self._long_ukrainian_block(4))

    def test_rejects_too_short(self) -> None:
        assert not PoemFileParser.looks_like_poem("коротко")

    def test_rejects_too_few_lines(self) -> None:
        text = ("я " * 50).strip()  # one long line, plenty of chars
        assert not PoemFileParser.looks_like_poem(text)

    def test_rejects_too_long(self) -> None:
        oversized = "а" * 10_001
        assert not PoemFileParser.looks_like_poem(oversized)

    def test_rejects_empty(self) -> None:
        assert not PoemFileParser.looks_like_poem("")

    def test_rejects_text_without_ukrainian_letters(self) -> None:
        body = "\n".join(["english text only here lorem ipsum"] * 6)
        assert not PoemFileParser.looks_like_poem(body)


# ---------------------------------------------------------------------------
# parse_numbered_poems
# ---------------------------------------------------------------------------

class TestParseNumberedPoems:
    def _make_block(self, *lines: str) -> str:
        # Five lines is comfortably above looks_like_poem's min_lines=4.
        body = "\n".join(lines)
        return body + "\n" + ("слово " * 12).strip()

    def test_returns_empty_when_no_headers(self) -> None:
        result = PoemFileParser().parse_numbered_poems("просто текст без нумерації")
        assert result == []

    def test_extracts_title_and_body_for_headered_poem(self) -> None:
        block = self._make_block(
            "1. Весна в лісі",
            "тиха моя пісня",
            "лине над землею",
            "пелюстки летять",
            "весна іде",
        )
        result = PoemFileParser().parse_numbered_poems(block)
        assert len(result) == 1
        assert result[0].title == "Весна в лісі"
        assert "тиха моя пісня" in result[0].text

    def test_falls_back_to_first_body_line_when_header_has_no_title(self) -> None:
        block = self._make_block(
            "1.",
            "тиха пісня",
            "лине над землею",
            "пелюстки летять",
            "весна іде",
        )
        result = PoemFileParser().parse_numbered_poems(block)
        assert len(result) == 1
        # The first body line is used as the title; it is dropped from the body.
        assert result[0].title == "тиха пісня"
        assert "тиха пісня" not in result[0].text

    def test_skips_blocks_that_do_not_look_like_poems(self) -> None:
        # Block 1 is too short to pass looks_like_poem; block 2 is fine.
        block = (
            "1. Ноотатка\nкоротко\n\n"
            "2. Поезія\n"
            "слово одне слово два слово три\n"
            "слово чотири слово п'ять слово шість\n"
            "слово сім слово вісім слово дев'ять\n"
            "слово десять слово одинадцять слово дванадцять\n"
        )
        result = PoemFileParser().parse_numbered_poems(block)
        ids = [p.title for p in result]
        assert ids == ["Поезія"]

    def test_handles_multiple_consecutive_numbered_blocks(self) -> None:
        block = (
            "1. Перший\n"
            "слово одне слово два слово три\n"
            "слово чотири слово п'ять слово шість\n"
            "слово сім слово вісім слово дев'ять\n"
            "слово десять слово одинадцять слово дванадцять\n\n"
            "2. Другий\n"
            "інше одне інше два інше три\n"
            "інше чотири інше п'ять інше шість\n"
            "інше сім інше вісім інше дев'ять\n"
            "інше десять інше одинадцять інше дванадцять\n"
        )
        result = PoemFileParser().parse_numbered_poems(block)
        titles = [p.title for p in result]
        assert titles == ["Перший", "Другий"]


# ---------------------------------------------------------------------------
# author_from_path
# ---------------------------------------------------------------------------

class TestAuthorFromPath:
    def test_returns_first_path_segment_relative_to_data_dir(self) -> None:
        author = PoemFileParser.author_from_path(
            Path("/data/shevchenko/kobzar/01.txt"),
            Path("/data"),
        )
        assert author == "shevchenko"

    def test_returns_none_when_file_sits_directly_in_data_dir(self) -> None:
        # `relative_to` succeeds but only one segment exists — no author.
        author = PoemFileParser.author_from_path(
            Path("/data/loose.txt"),
            Path("/data"),
        )
        assert author is None

    def test_returns_none_when_path_outside_data_dir(self) -> None:
        author = PoemFileParser.author_from_path(
            Path("/elsewhere/some.txt"),
            Path("/data"),
        )
        assert author is None
