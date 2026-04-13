"""Unit tests for BuildMetricCorpusRunner."""
from __future__ import annotations

import json
from pathlib import Path

from src.domain.detection import DetectionResult, MeterDetection, RhymeDetection
from src.domain.ports.detection import IDetectionService
from src.infrastructure.corpus.poem_file_parser import PoemFileParser
from src.infrastructure.logging import CollectingLogger
from src.runners.build_metric_corpus_runner import (
    BuildMetricCorpusRunner,
    BuildMetricCorpusRunnerConfig,
)


class _AlwaysDetects(IDetectionService):
    def detect(self, poem_text: str, sample_lines: int | None = None) -> DetectionResult:
        return DetectionResult(
            meter=MeterDetection(meter="ямб", foot_count=4, accuracy=0.95),
            rhyme=RhymeDetection(scheme="ABAB", accuracy=0.9),
        )


class _NeverDetects(IDetectionService):
    def detect(self, poem_text: str, sample_lines: int | None = None) -> DetectionResult:
        return DetectionResult(meter=None, rhyme=None)


class _MeterOnly(IDetectionService):
    def detect(self, poem_text: str, sample_lines: int | None = None) -> DetectionResult:
        return DetectionResult(
            meter=MeterDetection(meter="хорей", foot_count=4, accuracy=0.85),
            rhyme=None,
        )


class TestBuildMetricCorpusRunner:
    def test_no_txt_files_returns_exit_1(self, tmp_path: Path) -> None:
        logger = CollectingLogger()
        runner = BuildMetricCorpusRunner(
            config=BuildMetricCorpusRunnerConfig(
                data_dir=str(tmp_path),
                out_path=str(tmp_path / "out.json"),
            ),
            parser=PoemFileParser(),
            logger=logger,
            detection_service=_NeverDetects(),
        )
        assert runner.run() == 1

    def test_builds_metric_corpus(self, tmp_path: Path) -> None:
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

        out_path = tmp_path / "metric_corpus.json"
        logger = CollectingLogger()
        runner = BuildMetricCorpusRunner(
            config=BuildMetricCorpusRunnerConfig(
                data_dir=str(tmp_path / "data"),
                out_path=str(out_path),
            ),
            parser=PoemFileParser(),
            logger=logger,
            detection_service=_AlwaysDetects(),
        )
        assert runner.run() == 0
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["meter"] == "ямб"
        assert data[0]["feet"] == 4
        assert data[0]["scheme"] == "ABAB"
        assert data[0]["verified"] is False

    def test_skips_undetected_poems(self, tmp_path: Path) -> None:
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

        out_path = tmp_path / "metric_corpus.json"
        logger = CollectingLogger()
        runner = BuildMetricCorpusRunner(
            config=BuildMetricCorpusRunnerConfig(
                data_dir=str(tmp_path / "data"),
                out_path=str(out_path),
            ),
            parser=PoemFileParser(),
            logger=logger,
            detection_service=_NeverDetects(),
        )
        assert runner.run() == 0
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data == []
        # No drafts file when nothing was partially detected
        draft_path = out_path.with_stem(out_path.stem + "_drafts")
        assert not draft_path.exists()

    def test_partial_detection_saved_to_drafts(self, tmp_path: Path) -> None:
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

        out_path = tmp_path / "metric_corpus.json"
        logger = CollectingLogger()
        runner = BuildMetricCorpusRunner(
            config=BuildMetricCorpusRunnerConfig(
                data_dir=str(tmp_path / "data"),
                out_path=str(out_path),
            ),
            parser=PoemFileParser(),
            logger=logger,
            detection_service=_MeterOnly(),
        )
        assert runner.run() == 0

        # Main corpus is empty (no full detection)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data == []

        # Drafts file has partial results
        draft_path = out_path.with_stem(out_path.stem + "_drafts")
        assert draft_path.exists()
        drafts = json.loads(draft_path.read_text(encoding="utf-8"))
        assert len(drafts) >= 1
        assert drafts[0]["meter"] == "хорей"
        assert drafts[0]["scheme"] == ""
        assert drafts[0]["source"] == "auto-detected-partial"
