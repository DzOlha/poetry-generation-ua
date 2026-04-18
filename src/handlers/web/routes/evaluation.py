"""Web UI — evaluation routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from src.config import LLMInfo
from src.domain.errors import DomainError
from src.domain.evaluation import AblationConfig
from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest
from src.domain.ports import IScenarioRegistry
from src.handlers.api.dependencies import (
    get_ablation_configs,
    get_evaluation_service,
    get_llm_info,
    get_poetry_service,
    get_scenario_registry,
)
from src.handlers.shared.line_displays import line_displays as _line_displays
from src.handlers.web.routes._shared import scenarios_by_cat, templates
from src.services.evaluation_service import EvaluationService
from src.services.poetry_service import PoetryService

router = APIRouter()


def _build_line_displays(
    poem_text: str,
    scenario_meter: str,
    scenario_foot_count: int,
    scenario_rhyme: str,
    poetry: PoetryService,
) -> list[dict[str, object]]:
    """Validate a poem against the scenario and build per-line displays, or [] on failure."""
    if not poem_text or not poem_text.strip():
        return []
    try:
        meter_spec = MeterSpec(name=scenario_meter, foot_count=scenario_foot_count)
        rhyme = RhymeScheme(pattern=scenario_rhyme)
        validation = poetry.validate(ValidationRequest(
            poem_text=poem_text, meter=meter_spec, rhyme=rhyme,
        ))
        return _line_displays(poem_text, validation.meter.line_results)
    except DomainError:
        return []


@router.get("/evaluate", response_class=HTMLResponse)
def evaluate_form(
    request: Request,
    registry: IScenarioRegistry = Depends(get_scenario_registry),
    ablation_configs: list[AblationConfig] = Depends(get_ablation_configs),
    llm_info: LLMInfo = Depends(get_llm_info),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="evaluate.html", context={
            "scenarios_by_cat": scenarios_by_cat(registry),
            "ablation_configs": ablation_configs,
            "llm_info": llm_info,
        },
    )


@router.post("/evaluate", response_class=HTMLResponse)
def evaluate_run(
    request: Request,
    scenario_id: str = Form(...),
    config_label: str = Form("E"),
    max_iterations: int = Form(1, ge=0, le=3),
    eval_service: EvaluationService = Depends(get_evaluation_service),
    poetry: PoetryService = Depends(get_poetry_service),
    registry: IScenarioRegistry = Depends(get_scenario_registry),
    ablation_configs: list[AblationConfig] = Depends(get_ablation_configs),
    llm_info: LLMInfo = Depends(get_llm_info),
) -> HTMLResponse:
    # Same guard as /generate — abort before touching the pipeline if the
    # LLM stack isn't ready to do real generation.
    if not llm_info.ready:
        return templates.TemplateResponse(
            request=request, name="error.html",
            context={"error": llm_info.error},
        )
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

    final_line_displays = _build_line_displays(
        trace.final_poem,
        scenario.meter, scenario.foot_count, scenario.rhyme_scheme,
        poetry,
    )
    iteration_displays = [
        _build_line_displays(
            it.poem_text,
            scenario.meter, scenario.foot_count, scenario.rhyme_scheme,
            poetry,
        )
        for it in trace.iterations
    ]

    return templates.TemplateResponse(
        request=request, name="evaluate_result.html", context={
            "scenario": scenario,
            "config": config,
            "trace": trace,
            "stages": trace.stages,
            "iterations": trace.iterations,
            "final_metrics": trace.final_metrics,
            "final_line_displays": final_line_displays,
            "iteration_displays": iteration_displays,
        },
    )
