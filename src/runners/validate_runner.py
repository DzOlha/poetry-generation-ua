"""ValidateRunner — IRunner for the `validate` CLI command."""
from __future__ import annotations

from dataclasses import dataclass

from src.composition_root import (
    build_feedback_formatter,
    build_logger,
    build_poetry_service,
)
from src.config import AppConfig
from src.domain.errors import DomainError, UnsupportedConfigError
from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest
from src.domain.ports import IFeedbackFormatter, ILogger, IRunner, format_all_feedback
from src.services.poetry_service import PoetryService


@dataclass
class ValidateRunnerConfig:
    """All parameters for a single `validate` invocation."""

    poem_text: str
    meter: str = "ямб"
    feet: int = 4
    scheme: str = "ABAB"


class ValidateRunner(IRunner):
    """Validates an existing poem and emits results via the injected logger."""

    def __init__(
        self,
        app_config: AppConfig,
        config: ValidateRunnerConfig,
        logger: ILogger | None = None,
        poetry_service: PoetryService | None = None,
        formatter: IFeedbackFormatter | None = None,
    ) -> None:
        self._app_config = app_config
        self._cfg = config
        self._logger: ILogger = logger or build_logger(app_config)
        self._service = poetry_service
        self._formatter = formatter or build_feedback_formatter()

    def run(self) -> int:
        cfg = self._cfg
        try:
            service = self._service or build_poetry_service(self._app_config, logger=self._logger)
        except DomainError as exc:
            self._logger.error("Failed to initialise PoetryService", error=str(exc))
            return 1

        try:
            request = ValidationRequest(
                poem_text=cfg.poem_text,
                meter=MeterSpec(name=cfg.meter, foot_count=cfg.feet),
                rhyme=RhymeScheme(pattern=cfg.scheme),
            )
        except UnsupportedConfigError as exc:
            self._logger.error("Invalid request", error=str(exc))
            return 1

        try:
            result = service.validate(request)
        except DomainError as exc:
            self._logger.error("Validation failed", error=str(exc))
            return 1

        self._logger.info(
            "Poem validated",
            valid=result.is_valid,
            meter_ok=result.meter.ok,
            rhyme_ok=result.rhyme.ok,
            meter_accuracy=result.meter.accuracy,
            rhyme_accuracy=result.rhyme.accuracy,
        )
        for fb in format_all_feedback(self._formatter, result.meter.feedback, result.rhyme.feedback):
            self._logger.info("feedback", text=fb)
        return 0
