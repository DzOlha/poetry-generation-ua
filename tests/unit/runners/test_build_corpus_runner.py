"""Unit tests for BuildCorpusRunner and PoemFileParser."""
from __future__ import annotations

import json
from pathlib import Path

from src.infrastructure.corpus.poem_file_parser import PoemFileParser
from src.infrastructure.logging import CollectingLogger
from src.runners.build_corpus_runner import BuildCorpusRunner, BuildCorpusRunnerConfig


class TestPoemFileParser:
    def test_normalize_poem_text_collapses_blanks(self) -> None:
        text = "рядок один\n\n\n\nрядок два\n"
        result = PoemFileParser.normalize_poem_text(text)
        assert "\n\n\n" not in result

    def test_looks_like_poem_requires_cyrillic(self) -> None:
        english_text = "This is an English text\nwith several lines\nbut no Cyrillic\ncharacters here"
        assert not PoemFileParser.looks_like_poem(english_text)

    def test_looks_like_poem_true_for_valid(self) -> None:
        poem = "Реве та стогне Дніпр широкий\nСердитий вітер завива\nІ додолу верби гне\nТо лани широкополі рядок ще"
        assert PoemFileParser.looks_like_poem(poem)

    def test_looks_like_poem_false_for_short(self) -> None:
        assert not PoemFileParser.looks_like_poem("коротко")

    def test_parse_numbered_poems(self) -> None:
        parser = PoemFileParser()
        text = (
            "1. Перший вірш\n"
            "Реве та стогне Дніпр широкий\n"
            "Сердитий вітер завива\n"
            "І додолу верби гне\n"
            "То лани широкополі що\n"
            "\n"
            "2. Другий вірш\n"
            "Ще не вмерла України\n"
            "Ні слава ні воля\n"
            "Ще нам браття молоді\n"
            "Усміхнеться доля що\n"
        )
        poems = parser.parse_numbered_poems(text)
        assert len(poems) >= 1
        assert poems[0].title is not None

    def test_parse_empty_returns_empty(self) -> None:
        parser = PoemFileParser()
        assert parser.parse_numbered_poems("no numbered poems here") == []

    def test_author_from_path(self) -> None:
        data_dir = Path("/data")
        path = Path("/data/shevchenko/poems.txt")
        assert PoemFileParser.author_from_path(path, data_dir) == "shevchenko"

    def test_author_from_path_no_subdir(self) -> None:
        data_dir = Path("/data")
        path = Path("/data/poems.txt")
        assert PoemFileParser.author_from_path(path, data_dir) is None


class TestBuildCorpusRunner:
    def test_no_txt_files_returns_exit_1(self, tmp_path: Path) -> None:
        logger = CollectingLogger()
        cfg = BuildCorpusRunnerConfig(
            data_dir=str(tmp_path),
            out_path=str(tmp_path / "out.json"),
            min_count=0,
        )
        runner = BuildCorpusRunner(config=cfg, parser=PoemFileParser(), logger=logger)
        code = runner.run()
        assert code == 1

    def test_builds_corpus_json(self, tmp_path: Path) -> None:
        # Create a minimal numbered-poem file
        data_dir = tmp_path / "data" / "author"
        data_dir.mkdir(parents=True)
        poem_lines = "\n".join([
            "1. Тестовий Вірш",
            "Реве та стогне Дніпр широкий сердитий вітер завива",
            "Сердитий вітер завива і додолу верби гне він",
            "І додолу верби гне то лани широкополі теж",
            "То лани широкополі що далеко розлягалися",
        ])
        (data_dir / "poems.txt").write_text(poem_lines, encoding="utf-8")

        out_path = tmp_path / "corpus.json"
        logger = CollectingLogger()
        cfg = BuildCorpusRunnerConfig(
            data_dir=str(tmp_path / "data"),
            out_path=str(out_path),
            min_count=0,
        )
        runner = BuildCorpusRunner(config=cfg, parser=PoemFileParser(), logger=logger)
        code = runner.run()
        assert code == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
