"""GenerateRunner — IRunner for the `generate` CLI command and the pipeline demo.

Collapses the previous `GenerateRunner` + `PipelineRunner` pair into one
runner: every caller that used to build either one ends up here.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.composition_root import (
    build_feedback_formatter,
    build_logger,
    build_poetry_service,
)
from src.config import AppConfig
from src.domain.errors import DomainError, UnsupportedConfigError
from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme
from src.domain.ports import IFeedbackFormatter, ILogger, IRunner, format_all_feedback
from src.services.poetry_service import PoetryService


@dataclass
class GenerateRunnerConfig:
    """All parameters for a single `generate` invocation."""

    theme: str = "весна у лісі"
    meter: str = "ямб"
    feet: int = 4
    scheme: str = "ABAB"
    stanzas: int = 2
    lines_per_stanza: int = 4
    iterations: int = 3
    top_k: int = 5


class GenerateRunner(IRunner):
    """Generates a Ukrainian poem and emits the result via the injected logger."""

    def __init__(
        self,
        app_config: AppConfig,
        config: GenerateRunnerConfig,
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
            request = GenerationRequest(
                theme=cfg.theme,
                meter=MeterSpec(name=cfg.meter, foot_count=cfg.feet),
                rhyme=RhymeScheme(pattern=cfg.scheme),
                structure=PoemStructure(
                    stanza_count=cfg.stanzas,
                    lines_per_stanza=cfg.lines_per_stanza,
                ),
                max_iterations=cfg.iterations,
                top_k=cfg.top_k,
            )
        except UnsupportedConfigError as exc:
            self._logger.error("Invalid request", error=str(exc))
            return 1

        self._logger.info(
            "Generating poem",
            theme=cfg.theme,
            meter=cfg.meter,
            feet=cfg.feet,
            scheme=cfg.scheme,
            llm=service.llm_name,
        )

        try:
            result = service.generate(request)
        except DomainError as exc:
            self._logger.error("Generation failed", error=str(exc))
            return 1

        v = result.validation
        self._logger.info(
            "Poem generated",
            theme=cfg.theme,
            meter=cfg.meter,
            feet=cfg.feet,
            scheme=cfg.scheme,
            meter_ok=v.meter.ok,
            rhyme_ok=v.rhyme.ok,
            meter_accuracy=v.meter.accuracy,
            rhyme_accuracy=v.rhyme.accuracy,
            iterations=v.iterations,
        )
        for line in result.poem.splitlines():
            self._logger.info(line)
        for fb in format_all_feedback(self._formatter, v.meter.feedback, v.rhyme.feedback):
            self._logger.info("feedback", text=fb)
        return 0
