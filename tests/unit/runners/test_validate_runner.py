"""Unit tests for ValidateRunner."""
from __future__ import annotations

from dataclasses import replace as dc_replace

from src.config import AppConfig
from src.infrastructure.feedback import UkrainianFeedbackFormatter
from src.infrastructure.logging import CollectingLogger
from src.runners.validate_runner import ValidateRunner, ValidateRunnerConfig


class TestValidateRunner:
    def test_runs_successfully(self, poetry_service) -> None:
        logger = CollectingLogger()
        cfg = ValidateRunnerConfig(poem_text="Реве та стогне Дніпр широкий\nСердитий вітер завива")
        runner = ValidateRunner(
            app_config=dc_replace(AppConfig.from_env(), offline_embedder=True),
            config=cfg,
            logger=logger,
            poetry_service=poetry_service,
            formatter=UkrainianFeedbackFormatter(),
        )
        code = runner.run()
        assert code == 0
        messages = [r[1] for r in logger.records]
        assert any("Poem validated" in m for m in messages)

    def test_invalid_meter_returns_exit_1(self) -> None:
        logger = CollectingLogger()
        cfg = ValidateRunnerConfig(
            poem_text="рядок",
            meter="гекзаметр",
        )
        runner = ValidateRunner(
            app_config=dc_replace(AppConfig.from_env(), offline_embedder=True),
            config=cfg,
            logger=logger,
        )
        code = runner.run()
        assert code == 1


class TestValidateRunnerValidation:
    def test_reports_accuracy(self, poetry_service) -> None:
        logger = CollectingLogger()
        cfg = ValidateRunnerConfig(
            poem_text="Реве та стогне Дніпр широкий\nСердитий вітер завива\nІ додолу верби гне\nТо лани широкополі",
        )
        runner = ValidateRunner(
            app_config=dc_replace(AppConfig.from_env(), offline_embedder=True),
            config=cfg,
            logger=logger,
            poetry_service=poetry_service,
            formatter=UkrainianFeedbackFormatter(),
        )
        code = runner.run()
        assert code == 0
        # Check that accuracy was logged
        info_records = [(m, f) for lvl, m, f in logger.records if lvl == "info"]
        validated_msgs = [(m, f) for m, f in info_records if "Poem validated" in m]
        assert len(validated_msgs) == 1
