"""Unit tests for GenerateRunner and EvaluationRunner."""
from __future__ import annotations

import json
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest

from src.composition_root import build_evaluation_service
from src.config import AppConfig
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.logging import CollectingLogger
from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder
from src.runners.evaluation_runner import EvaluationRunner, EvaluationRunnerConfig
from src.runners.generate_runner import GenerateRunner, GenerateRunnerConfig
from src.services.evaluation_service import EvaluationService

# ---------------------------------------------------------------------------
# GenerateRunner
# ---------------------------------------------------------------------------

class TestGenerateRunner:
    def test_runs_successfully(self, poetry_service):
        logger = CollectingLogger()
        runner = GenerateRunner(
            app_config=AppConfig.from_env(),
            config=GenerateRunnerConfig(theme="весна", iterations=1, stanzas=1),
            logger=logger,
            poetry_service=poetry_service,
        )
        assert runner.run() == 0
        messages = [msg for _, msg, _ in logger.records]
        assert "Generating poem" in messages
        assert "Poem generated" in messages


# ---------------------------------------------------------------------------
# EvaluationRunner
# ---------------------------------------------------------------------------

@pytest.fixture
def eval_service() -> EvaluationService:
    cfg = dc_replace(AppConfig.from_env(), offline_embedder=True)
    logger = CollectingLogger()
    llm = MockLLMProvider(regeneration_prompt_builder=NumberedLinesRegenerationPromptBuilder())
    return build_evaluation_service(cfg, logger=logger, llm=llm)


class TestEvaluationRunner:
    def test_runs_single_scenario_single_config(self, eval_service):
        logger = CollectingLogger()
        cfg = EvaluationRunnerConfig(
            scenario_id="N01",
            config_label="A",
            max_iterations=1,
        )
        runner = EvaluationRunner(
            app_config=AppConfig.from_env(),
            config=cfg,
            logger=logger,
            service=eval_service,
        )
        assert runner.run() == 0
        assert any(msg == "Starting evaluation" for _, msg, _ in logger.records)

    def test_unknown_scenario_returns_error(self, eval_service):
        logger = CollectingLogger()
        cfg = EvaluationRunnerConfig(scenario_id="ZZZZ")
        runner = EvaluationRunner(
            app_config=AppConfig.from_env(),
            config=cfg,
            logger=logger,
            service=eval_service,
        )
        assert runner.run() == 1

    def test_unknown_config_returns_error(self, eval_service):
        logger = CollectingLogger()
        cfg = EvaluationRunnerConfig(config_label="Z")
        runner = EvaluationRunner(
            app_config=AppConfig.from_env(),
            config=cfg,
            logger=logger,
            service=eval_service,
        )
        assert runner.run() == 1

    def test_saves_json_and_markdown_when_output_set(self, eval_service, tmp_path: Path):
        out = tmp_path / "results" / "eval.json"
        logger = CollectingLogger()
        runner = EvaluationRunner(
            app_config=AppConfig.from_env(),
            config=EvaluationRunnerConfig(
                scenario_id="N01",
                config_label="A",
                output_path=str(out),
            ),
            logger=logger,
            service=eval_service,
        )
        assert runner.run() == 0
        assert out.exists()
        md = out.with_suffix(".md")
        assert md.exists()
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert "summary" in payload
        assert "traces" in payload
