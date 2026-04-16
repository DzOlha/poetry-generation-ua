"""CLI entry point — generate, validate, and evaluate Ukrainian poetry from the terminal.

Every command delegates to an `IRunner` implementation; the CLI itself is
purely an argparse/Click adapter.
"""
from __future__ import annotations

import sys

import click

from src.config import AppConfig
from src.runners.detect_runner import DetectRunner, DetectRunnerConfig
from src.runners.evaluation_runner import EvaluationRunner, EvaluationRunnerConfig
from src.runners.generate_runner import GenerateRunner, GenerateRunnerConfig
from src.runners.validate_runner import ValidateRunner, ValidateRunnerConfig

_METERS = ["ямб", "хорей", "дактиль", "амфібрахій", "анапест"]
_SCHEMES = ["ABAB", "AABB", "ABBA", "AAAA"]


@click.group()
def cli() -> None:
    """Ukrainian poetry generation and validation CLI."""


@cli.command()
@click.option("--theme", required=True)
@click.option("--meter", default="ямб", show_default=True, type=click.Choice(_METERS))
@click.option("--feet", default=4, show_default=True, type=int)
@click.option("--scheme", default="ABAB", show_default=True, type=click.Choice(_SCHEMES))
@click.option("--stanzas", default=4, show_default=True, type=int)
@click.option("--lines", default=4, show_default=True, type=int)
@click.option("--iterations", default=3, show_default=True, type=int)
@click.option("--top-k", default=5, show_default=True, type=int)
def generate(
    theme: str,
    meter: str,
    feet: int,
    scheme: str,
    stanzas: int,
    lines: int,
    iterations: int,
    top_k: int,
) -> None:
    """Generate a Ukrainian poem with the specified constraints."""
    runner = GenerateRunner(
        app_config=AppConfig.from_env(),
        config=GenerateRunnerConfig(
            theme=theme,
            meter=meter,
            feet=feet,
            scheme=scheme,
            stanzas=stanzas,
            lines_per_stanza=lines,
            iterations=iterations,
            top_k=top_k,
        ),
    )
    sys.exit(runner.run())


@cli.command()
@click.argument("poem_text", required=False)
@click.option("--poem-file", type=click.Path(exists=True))
@click.option("--meter", default="ямб", show_default=True, type=click.Choice(_METERS))
@click.option("--feet", default=4, show_default=True, type=int)
@click.option("--scheme", default="ABAB", show_default=True, type=click.Choice(_SCHEMES))
def validate(
    poem_text: str | None,
    poem_file: str | None,
    meter: str,
    feet: int,
    scheme: str,
) -> None:
    """Validate a poem against meter and rhyme constraints."""
    if poem_file:
        try:
            with open(poem_file, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            raise click.BadParameter(f"Cannot read poem file: {exc}") from exc
    elif poem_text:
        text = poem_text
    else:
        raise click.UsageError("Provide POEM_TEXT argument or --poem-file.")

    runner = ValidateRunner(
        app_config=AppConfig.from_env(),
        config=ValidateRunnerConfig(
            poem_text=text,
            meter=meter,
            feet=feet,
            scheme=scheme,
        ),
    )
    sys.exit(runner.run())


@cli.command()
@click.option("--scenario", default=None)
@click.option("--category", default=None, type=click.Choice(["normal", "edge", "corner"]))
@click.option("--config", default=None, type=click.Choice(["A", "B", "C", "D", "E"]))
@click.option("--max-iterations", default=1, show_default=True, type=int)
@click.option("--stanzas", default=None, type=int)
@click.option("--lines", default=None, type=int)
@click.option("--output", "-o", default=None)
@click.option("--verbose", "-v", is_flag=True)
def evaluate(
    scenario: str | None,
    category: str | None,
    config: str | None,
    max_iterations: int,
    stanzas: int | None,
    lines: int | None,
    output: str | None,
    verbose: bool,
) -> None:
    """Run evaluation scenarios through ablation configs with full tracing."""
    runner = EvaluationRunner(
        app_config=AppConfig.from_env(),
        config=EvaluationRunnerConfig(
            scenario_id=scenario,
            category=category,
            config_label=config,
            max_iterations=max_iterations,
            stanzas=stanzas,
            lines_per_stanza=lines,
            output_path=output,
            verbose=verbose,
        ),
    )
    sys.exit(runner.run())


@cli.command()
@click.argument("poem_text", required=False)
@click.option("--poem-file", type=click.Path(exists=True))
@click.option("--sample-lines", default=4, type=int, help="Stanza size (fixed at 4).")
def detect(
    poem_text: str | None,
    poem_file: str | None,
    sample_lines: int | None,
) -> None:
    """Detect meter and rhyme scheme of a poem automatically."""
    if poem_file:
        try:
            with open(poem_file, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            raise click.BadParameter(f"Cannot read poem file: {exc}") from exc
    elif poem_text:
        text = poem_text
    else:
        raise click.UsageError("Provide POEM_TEXT argument or --poem-file.")

    runner = DetectRunner(
        app_config=AppConfig.from_env(),
        config=DetectRunnerConfig(
            poem_text=text,
            sample_lines=sample_lines,
        ),
    )
    sys.exit(runner.run())


if __name__ == "__main__":
    cli()
