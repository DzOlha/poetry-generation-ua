"""FastAPI dependency injection — wires services into route handlers.

Every dependency is resolved through `request.app.state` so test fixtures
can swap implementations via `app.dependency_overrides[get_X] = ...`
without monkey-patching modules. Module-level singletons are forbidden.
"""
from __future__ import annotations

from fastapi import Request

from src.config import LLMInfo
from src.domain.evaluation import AblationConfig
from src.domain.ports import IFeedbackFormatter, IMetricCalculatorRegistry, IScenarioRegistry
from src.services.detection_service import DetectionService
from src.services.evaluation_service import EvaluationService
from src.services.poetry_service import PoetryService


def get_poetry_service(request: Request) -> PoetryService:
    """Return the singleton PoetryService built at app startup."""
    return request.app.state.poetry_service


def get_evaluation_service(request: Request) -> EvaluationService:
    """Return the singleton EvaluationService built at app startup."""
    return request.app.state.evaluation_service


def get_feedback_formatter(request: Request) -> IFeedbackFormatter:
    """Return the IFeedbackFormatter built at app startup."""
    return request.app.state.feedback_formatter


def get_scenario_registry(request: Request) -> IScenarioRegistry:
    """Return the IScenarioRegistry built at app startup."""
    return request.app.state.scenario_registry


def get_ablation_configs(request: Request) -> list[AblationConfig]:
    """Return the list of AblationConfig instances built at app startup."""
    return request.app.state.ablation_configs


def get_detection_service(request: Request) -> DetectionService:
    """Return the singleton DetectionService built at app startup."""
    return request.app.state.detection_service


def get_metric_registry(request: Request) -> IMetricCalculatorRegistry:
    """Return the container's IMetricCalculatorRegistry."""
    return request.app.state.container.metric_registry()


def get_llm_info(request: Request) -> LLMInfo:
    """Return the active LLM provider / model metadata and readiness flag."""
    return request.app.state.llm_info
