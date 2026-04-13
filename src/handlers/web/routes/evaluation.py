"""Web UI — evaluation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.domain.errors import DomainError
from src.domain.evaluation import AblationConfig
from src.domain.ports import IScenarioRegistry
from src.handlers.api.dependencies import (
    get_ablation_configs,
    get_evaluation_service,
    get_scenario_registry,
)
from src.handlers.web.routes._shared import scenarios_by_cat, templates
from src.services.evaluation_service import EvaluationService

router = APIRouter()


@router.get("/evaluate", response_class=HTMLResponse)
def evaluate_form(
    request: Request,
    registry: IScenarioRegistry = Depends(get_scenario_registry),
    ablation_configs: list[AblationConfig] = Depends(get_ablation_configs),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="evaluate.html", context={
            "scenarios_by_cat": scenarios_by_cat(registry),
            "ablation_configs": ablation_configs,
        },
    )


@router.post("/evaluate", response_class=HTMLResponse)
def evaluate_run(
    request: Request,
    scenario_id: str = Form(...),
    config_label: str = Form("E"),
    max_iterations: int = Form(1),
    eval_service: EvaluationService = Depends(get_evaluation_service),
    registry: IScenarioRegistry = Depends(get_scenario_registry),
    ablation_configs: list[AblationConfig] = Depends(get_ablation_configs),
) -> HTMLResponse:
    scenario = registry.by_id(scenario_id.upper())
    if scenario is None:
        return templates.TemplateResponse(
            request=request, name="evaluate.html", context={
                "error": f"Unknown scenario ID: {scenario_id}",
                "scenarios_by_cat": scenarios_by_cat(registry),
                "ablation_configs": ablation_configs,
            },
        )

    config = next(
        (c for c in ablation_configs if c.label == config_label.upper()),
        ablation_configs[-1],
    )
    try:
        trace = eval_service.run_scenario(
            scenario, config,
            max_iterations=max_iterations,
        )
    except DomainError as exc:
        return templates.TemplateResponse(
            request=request, name="evaluate.html", context={
                "error": str(exc),
                "scenarios_by_cat": scenarios_by_cat(registry),
                "ablation_configs": ablation_configs,
            },
        )
    return templates.TemplateResponse(
        request=request, name="evaluate_result.html", context={
            "scenario": scenario,
            "config": config,
            "trace": trace,
            "stages": trace.stages,
            "iterations": trace.iterations,
            "final_metrics": trace.final_metrics,
        },
    )
