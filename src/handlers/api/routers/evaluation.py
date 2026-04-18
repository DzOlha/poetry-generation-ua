"""Evaluation API routes — ablation configs, scenarios, and scenario runs.

Exposes the same data the HTML `/evaluate` page consumes so an SPA can
render the full pipeline trace: scenario + config metadata, stage-by-stage
records with input/output data, iteration poems with annotated line
displays, and final metrics.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

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
from src.handlers.api.schemas import (
    AblationConfigSchema,
    EvaluationRunRequestSchema,
    EvaluationRunResponseSchema,
    LineDisplaySchema,
    PipelineTraceSchema,
    ScenarioSchema,
)
from src.services.evaluation_service import EvaluationService
from src.services.poetry_service import PoetryService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/scenarios", response_model=list[ScenarioSchema])
def list_scenarios(
    registry: IScenarioRegistry = Depends(get_scenario_registry),
) -> list[ScenarioSchema]:
    """Return every evaluation scenario known to the system (18 predefined)."""
    return [ScenarioSchema.from_domain(s) for s in registry.all]


@router.get("/configs", response_model=list[AblationConfigSchema])
def list_configs(
    configs: list[AblationConfig] = Depends(get_ablation_configs),
) -> list[AblationConfigSchema]:
    """Return every ablation configuration (A–E) with its enabled stages."""
    return [AblationConfigSchema.from_domain(c) for c in configs]


def _build_line_displays(
    poem_text: str,
    meter: str, foot_count: int, rhyme: str,
    poetry: PoetryService,
) -> list[LineDisplaySchema]:
    """Validate a scenario-run poem to produce per-line annotated displays.

    Wraps DomainError: a degenerate scenario (unsupported meter, empty poem)
    collapses to an empty list rather than failing the whole response.
    """
    if not poem_text or not poem_text.strip():
        return []
    try:
        validation = poetry.validate(ValidationRequest(
            poem_text=poem_text,
            meter=MeterSpec(name=meter, foot_count=foot_count),
            rhyme=RhymeScheme(pattern=rhyme),
        ))
        return LineDisplaySchema.list_from(poem_text, validation.meter.line_results)
    except DomainError:
        return []


@router.post("/run", response_model=EvaluationRunResponseSchema)
def run_evaluation(
    body: EvaluationRunRequestSchema,
    eval_service: EvaluationService = Depends(get_evaluation_service),
    poetry: PoetryService = Depends(get_poetry_service),
    registry: IScenarioRegistry = Depends(get_scenario_registry),
    configs: list[AblationConfig] = Depends(get_ablation_configs),
    llm_info: LLMInfo = Depends(get_llm_info),
) -> EvaluationRunResponseSchema:
    """Run a scenario through an ablation config and return the full trace.

    Response mirrors the HTML `/evaluate_result.html` page: stage-by-stage
    records, iteration history with annotated poems, and final metrics.
    """
    if not llm_info.ready:
        raise HTTPException(status_code=503, detail=llm_info.error)
    scenario = registry.by_id(body.scenario_id.upper())
    if scenario is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown scenario ID: {body.scenario_id}",
        )

    config = next(
        (c for c in configs if c.label == body.config_label.upper()),
        configs[-1],
    )

    try:
        trace = eval_service.run_scenario(
            scenario, config, max_iterations=body.max_iterations,
        )
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Enrich trace with per-poem line displays so the SPA never needs to
    # call /poems/validate separately just to render highlights.
    final_displays = _build_line_displays(
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

    return EvaluationRunResponseSchema(
        scenario=ScenarioSchema.from_domain(scenario),
        config=AblationConfigSchema.from_domain(config),
        trace=PipelineTraceSchema.from_domain(
            trace,
            final_line_displays=final_displays,
            iteration_line_displays=iteration_displays,
        ),
    )
