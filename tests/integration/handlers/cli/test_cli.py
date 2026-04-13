"""Integration tests for the Click CLI handler."""
from __future__ import annotations

import pytest

try:
    from click.testing import CliRunner
except ImportError:  # pragma: no cover
    pytest.skip("click not installed", allow_module_level=True)

from src.handlers.cli.main import cli


@pytest.fixture(scope="module")
def runner() -> CliRunner:
    return CliRunner()


def _isolate_env(monkeypatch) -> None:
    """Force the offline embedder and the MockLLMProvider so tests never
    reach the real Gemini API or download LaBSE weights."""
    monkeypatch.setenv("OFFLINE_EMBEDDER", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.mark.integration
class TestCliGenerate:
    def test_generate_prints_poem(self, runner: CliRunner, monkeypatch):
        _isolate_env(monkeypatch)
        result = runner.invoke(
            cli,
            [
                "generate",
                "--theme", "весна",
                "--meter", "ямб",
                "--feet", "4",
                "--scheme", "ABAB",
                "--stanzas", "1",
                "--lines", "4",
                "--iterations", "1",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Generating poem" in result.output
        assert "Poem generated" in result.output
        assert "meter=" in result.output


@pytest.mark.integration
class TestCliValidate:
    def test_validate_accepts_poem_argument(self, runner: CliRunner, monkeypatch):
        _isolate_env(monkeypatch)
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "І спів пташок в гіллі бринить.\n"
            "Струмок біжить, мов шлях натхнений,\n"
            "І сонце крізь туман горить.\n"
        )
        result = runner.invoke(cli, ["validate", poem])
        assert result.exit_code == 0, result.output
        assert "Poem validated" in result.output


@pytest.mark.integration
class TestCliEvaluate:
    def test_evaluate_runs_single_scenario(self, runner: CliRunner, monkeypatch):
        _isolate_env(monkeypatch)
        result = runner.invoke(
            cli,
            ["evaluate", "--scenario", "N01", "--config", "A"],
        )
        assert result.exit_code == 0, result.output
