"""Web UI — ablation-report page.

Renders the latest ablation-batch dashboard. The artifact-building
logic lives in :mod:`src.handlers.shared.ablation_report` so the JSON
API endpoint can return the same payload an SPA would otherwise have
to scrape from this HTML page.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.domain.ports import IScenarioRegistry
from src.handlers.api.dependencies import get_scenario_registry
from src.handlers.shared.ablation_report import build_artifacts
from src.handlers.web.routes._shared import templates

router = APIRouter()

_RESULTS_DIR = Path(__file__).resolve().parents[4] / "results"


@router.get("/ablation-report", response_class=HTMLResponse)
def ablation_report(
    request: Request,
    registry: IScenarioRegistry = Depends(get_scenario_registry),
) -> HTMLResponse:
    artifacts = build_artifacts(_RESULTS_DIR, registry)
    return templates.TemplateResponse(
        request=request, name="ablation_report.html", context={
            "artifacts": artifacts,
        },
    )
