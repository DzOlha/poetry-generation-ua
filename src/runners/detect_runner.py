"""DetectRunner — IRunner that detects meter and rhyme of a single poem text."""
from __future__ import annotations

from dataclasses import dataclass

from src.composition_root import build_detection_service, build_logger
from src.config import AppConfig
from src.domain.errors import DomainError
from src.domain.ports import ILogger, IRunner
from src.domain.ports.detection import IDetectionService


@dataclass
class DetectRunnerConfig:
    poem_text: str = ""
    sample_lines: int | None = None


class DetectRunner(IRunner):
    """Detects meter and rhyme of a poem and prints the result."""

    def __init__(
        self,
        config: DetectRunnerConfig,
        app_config: AppConfig | None = None,
        logger: ILogger | None = None,
        detection_service: IDetectionService | None = None,
    ) -> None:
        self._cfg = config
        self._app_config = app_config or AppConfig.from_env()
        self._logger = logger or build_logger(self._app_config)
        self._detection = detection_service or build_detection_service(
            self._app_config, logger=self._logger,
        )

    def run(self) -> int:
        try:
            result = self._detection.detect(
                self._cfg.poem_text,
                sample_lines=self._cfg.sample_lines,
            )
        except DomainError as exc:
            self._logger.error("Detection failed", error=str(exc))
            return 1

        if result.meter:
            self._logger.info(
                "Meter detected",
                meter=result.meter.meter,
                feet=result.meter.foot_count,
                accuracy=f"{result.meter.accuracy:.0%}",
            )
        else:
            self._logger.info("No meter detected above threshold")

        if result.rhyme:
            self._logger.info(
                "Rhyme detected",
                scheme=result.rhyme.scheme,
                accuracy=f"{result.rhyme.accuracy:.0%}",
            )
        else:
            self._logger.info("No rhyme scheme detected above threshold")

        return 0
