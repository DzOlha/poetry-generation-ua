"""Shared utilities for web routes — templates and helpers."""
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from src.domain.ports import IScenarioRegistry
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def scenarios_by_cat(
    registry: IScenarioRegistry,
) -> dict[str, list[EvaluationScenario]]:
    return {
        "normal": list(registry.by_category(ScenarioCategory.NORMAL)),
        "edge": list(registry.by_category(ScenarioCategory.EDGE)),
        "corner": list(registry.by_category(ScenarioCategory.CORNER)),
    }
