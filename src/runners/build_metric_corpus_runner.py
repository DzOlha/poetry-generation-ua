"""BuildMetricCorpusRunner — IRunner that builds an auto-detected metric corpus.

Reads poems from ``data/`` (via ICorpusParser, same source as the theme corpus),
samples leading lines, runs brute-force meter/rhyme detection, and writes
qualifying poems to a JSON corpus file.

Independent from the theme corpus — both read ``data/`` directly.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from src.composition_root import build_detection_service, build_logger
from src.config import AppConfig
from src.domain.errors import DomainError, RepositoryError
from src.domain.metric_corpus_entry import MetricCorpusEntry
from src.domain.ports import ICorpusParser, ILogger, IRunner
from src.domain.ports.detection import IDetectionService


@dataclass
class BuildMetricCorpusRunnerConfig:
    data_dir: str = "data"
    out_path: str = "corpus/uk_auto_metric_corpus.json"
    sample_lines: int | None = None


class BuildMetricCorpusRunner(IRunner):
    """Scans data/ and emits a JSON corpus of metrically classified poems."""

    def __init__(
        self,
        config: BuildMetricCorpusRunnerConfig,
        parser: ICorpusParser,
        app_config: AppConfig | None = None,
        logger: ILogger | None = None,
        detection_service: IDetectionService | None = None,
    ) -> None:
        self._cfg = config
        self._app_config = app_config or AppConfig.from_env()
        self._logger = logger or build_logger(self._app_config)
        self._parser = parser
        self._detection = detection_service or build_detection_service(
            self._app_config, logger=self._logger,
        )

    def run(self) -> int:
        data_dir = Path(self._cfg.data_dir)
        out_path = Path(self._cfg.out_path)
        try:
            entries = self._build(data_dir, out_path)
        except DomainError as exc:
            self._logger.error("Metric corpus build failed", error=str(exc))
            return 1

        self._logger.info("Metric corpus built", entries=len(entries), out=str(out_path))
        return 0

    def _build(self, data_dir: Path, out_path: Path) -> list[MetricCorpusEntry]:
        files = sorted(p for p in data_dir.rglob("*.txt") if p.is_file())
        if not files:
            raise RepositoryError(f"No .txt files found under: {data_dir}")

        entries: list[MetricCorpusEntry] = []
        draft_count = 0
        seen_hashes: set[str] = set()
        sample_lines = self._cfg.sample_lines
        draft_path = out_path.with_stem(out_path.stem + "_drafts")
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text("[\n", encoding="utf-8")

        for f in files:
            raw = f.read_text(encoding="utf-8", errors="replace")
            parsed = self._parser.parse_numbered_poems(raw)
            author = self._parser.author_from_path(f, data_dir)

            for idx, poem in enumerate(parsed, start=1):
                h = hashlib.sha256(poem.text.encode("utf-8")).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)

                result = self._detection.detect(poem.text, sample_lines=sample_lines)

                self._logger.info(
                    "Detection complete",
                    author=author or "unknown",
                    title=poem.title or f"#{idx}",
                    meter=result.meter.meter if result.meter else None,
                    feet=result.meter.foot_count if result.meter else None,
                    scheme=result.rhyme.scheme if result.rhyme else None,
                )

                if result.is_detected:
                    assert result.meter is not None
                    assert result.rhyme is not None

                    entry_id = (
                        f"{result.meter.meter}_{result.meter.foot_count}"
                        f"_{result.rhyme.scheme}"
                        f"_{author or 'unknown'}_{f.stem}_{idx}"
                    )
                    entries.append(MetricCorpusEntry(
                        id=entry_id,
                        meter=result.meter.meter,
                        feet=result.meter.foot_count,
                        scheme=result.rhyme.scheme,
                        meter_accuracy=round(result.meter.accuracy, 4),
                        rhyme_accuracy=round(result.rhyme.accuracy, 4),
                        verified=False,
                        source="auto-detected",
                        author=author,
                        title=poem.title,
                        text=poem.text,
                    ))
                elif result.meter is not None or result.rhyme is not None:
                    draft_id = (
                        f"{result.meter.meter if result.meter else 'unknown'}"
                        f"_{result.meter.foot_count if result.meter else 0}"
                        f"_{result.rhyme.scheme if result.rhyme else 'unknown'}"
                        f"_{author or 'unknown'}_{f.stem}_{idx}"
                    )
                    draft_entry = MetricCorpusEntry(
                        id=draft_id,
                        meter=result.meter.meter if result.meter else "",
                        feet=result.meter.foot_count if result.meter else 0,
                        scheme=result.rhyme.scheme if result.rhyme else "",
                        meter_accuracy=round(result.meter.accuracy, 4) if result.meter else 0.0,
                        rhyme_accuracy=round(result.rhyme.accuracy, 4) if result.rhyme else 0.0,
                        verified=False,
                        source="auto-detected-partial",
                        author=author,
                        title=poem.title,
                        text=poem.text,
                    )
                    prefix = "  " if draft_count == 0 else ",\n  "
                    with draft_path.open("a", encoding="utf-8") as fp:
                        fp.write(prefix + json.dumps(draft_entry, ensure_ascii=False))
                    draft_count += 1

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with draft_path.open("a", encoding="utf-8") as fp:
            fp.write("\n]\n")

        if draft_count == 0:
            draft_path.unlink()
        else:
            self._logger.info(
                "Partial detections saved",
                drafts=draft_count,
                out=str(draft_path),
            )

        return entries
