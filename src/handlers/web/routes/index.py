"""Web UI — index page."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.domain.evaluation import AblationConfig
from src.domain.ports import IScenarioRegistry
from src.handlers.api.dependencies import get_ablation_configs, get_scenario_registry
from src.handlers.web.routes._shared import scenarios_by_cat, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    registry: IScenarioRegistry = Depends(get_scenario_registry),
    ablation_configs: list[AblationConfig] = Depends(get_ablation_configs),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "scenarios_by_cat": scenarios_by_cat(registry),
            "ablation_configs": ablation_configs,
        },
    )
