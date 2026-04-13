"""Unit tests for the CLI entry point."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.handlers.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestGenerateCommand:
    def test_generate_requires_theme(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    @patch("src.handlers.cli.main.GenerateRunner")
    def test_generate_calls_runner(self, mock_runner_cls: MagicMock, runner: CliRunner) -> None:
        mock_runner_cls.return_value.run.return_value = 0
        result = runner.invoke(cli, ["generate", "--theme", "весна"])
        assert result.exit_code == 0
        mock_runner_cls.return_value.run.assert_called_once()

    @patch("src.handlers.cli.main.GenerateRunner")
    def test_generate_passes_options(self, mock_runner_cls: MagicMock, runner: CliRunner) -> None:
        mock_runner_cls.return_value.run.return_value = 0
        result = runner.invoke(cli, [
            "generate", "--theme", "зима",
            "--meter", "хорей", "--feet", "3",
            "--scheme", "AABB", "--stanzas", "2", "--lines", "4",
            "--iterations", "5", "--top-k", "3",
        ])
        assert result.exit_code == 0
        call_kwargs = mock_runner_cls.call_args
        config = call_kwargs.kwargs["config"]
        assert config.theme == "зима"
        assert config.meter == "хорей"
        assert config.feet == 3
        assert config.scheme == "AABB"
        assert config.iterations == 5


class TestValidateCommand:
    @patch("src.handlers.cli.main.ValidateRunner")
    def test_validate_with_text(self, mock_runner_cls: MagicMock, runner: CliRunner) -> None:
        mock_runner_cls.return_value.run.return_value = 0
        result = runner.invoke(cli, ["validate", "мій вірш"])
        assert result.exit_code == 0
        mock_runner_cls.return_value.run.assert_called_once()

    @patch("src.handlers.cli.main.ValidateRunner")
    def test_validate_with_file(self, mock_runner_cls: MagicMock, runner: CliRunner, tmp_path) -> None:
        poem_file = tmp_path / "poem.txt"
        poem_file.write_text("рядок один\nрядок два\n", encoding="utf-8")
        mock_runner_cls.return_value.run.return_value = 0
        result = runner.invoke(cli, ["validate", "--poem-file", str(poem_file)])
        assert result.exit_code == 0

    def test_validate_missing_input(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code != 0

    def test_validate_nonexistent_file(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["validate", "--poem-file", "/nonexistent/file.txt"])
        assert result.exit_code != 0


class TestEvaluateCommand:
    @patch("src.handlers.cli.main.EvaluationRunner")
    def test_evaluate_default(self, mock_runner_cls: MagicMock, runner: CliRunner) -> None:
        mock_runner_cls.return_value.run.return_value = 0
        result = runner.invoke(cli, ["evaluate"])
        assert result.exit_code == 0
        mock_runner_cls.return_value.run.assert_called_once()

    @patch("src.handlers.cli.main.EvaluationRunner")
    def test_evaluate_with_options(self, mock_runner_cls: MagicMock, runner: CliRunner) -> None:
        mock_runner_cls.return_value.run.return_value = 0
        result = runner.invoke(cli, [
            "evaluate",
            "--scenario", "N01",
            "--category", "normal",
            "--config", "E",
            "--max-iterations", "3",
            "--verbose",
        ])
        assert result.exit_code == 0
        config = mock_runner_cls.call_args.kwargs["config"]
        assert config.scenario_id == "N01"
        assert config.category == "normal"
        assert config.config_label == "E"
        assert config.max_iterations == 3
        assert config.verbose is True
