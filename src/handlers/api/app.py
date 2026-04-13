"""FastAPI application factory.

Uses a single shared `Container` so `PoetryService` and `EvaluationService`
really share every memoised adapter (embedder, validators, LLM, prosody,
etc.) — previously they each built their own `_Container` and only the
LLM was wired across.

Also installs a single exception handler that routes every `DomainError`
through the injected `IHttpErrorMapper` so handlers never return a bare
`500 Internal Server Error` for errors the system is designed to raise.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.composition_root import (
    build_container,
    build_detection_service,
    build_evaluation_service,
    build_poetry_service,
)
from src.config import AppConfig
from src.domain.errors import DomainError
from src.domain.ports import IHttpErrorMapper
from src.handlers.api.routers.detection import router as detection_router
from src.handlers.api.routers.health import router as health_router
from src.handlers.api.routers.poems import router as poems_router
from src.handlers.web.router import router as web_router

_STATIC_DIR = Path(__file__).parent.parent / "web" / "static"


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = config or AppConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from src.domain.evaluation import ABLATION_CONFIGS

        container = build_container(cfg)
        poetry_service = build_poetry_service(cfg, container=container)
        app.state.app_config = cfg
        app.state.container = container
        app.state.poetry_service = poetry_service
        app.state.feedback_formatter = container.feedback_formatter()
        app.state.http_error_mapper = container.http_error_mapper()
        app.state.scenario_registry = container.scenario_registry()
        app.state.ablation_configs = ABLATION_CONFIGS
        app.state.evaluation_service = build_evaluation_service(
            cfg, container=container,
        )
        app.state.detection_service = build_detection_service(
            cfg, container=container,
        )
        try:
            yield
        finally:
            # Reserved for future cleanup hooks (close LLM clients, embedding
            # caches, etc.). Today there is nothing to release.
            pass

    app = FastAPI(
        title="Ukrainian Poetry Generator",
        description="Generate and validate Ukrainian poetry with meter and rhyme constraints.",
        version="2.0.0",
        lifespan=lifespan,
    )

    _install_domain_error_handler(app)

    app.include_router(health_router)
    app.include_router(poems_router)
    app.include_router(detection_router)
    app.include_router(web_router)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


def _install_domain_error_handler(app: FastAPI) -> None:
    """Translate every `DomainError` into an HTTP response via `IHttpErrorMapper`.

    The mapper is pulled from `app.state` on each request so tests can swap
    it via `app.dependency_overrides` or by mutating the state directly.
    """

    @app.exception_handler(DomainError)
    def _on_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        mapper: IHttpErrorMapper = request.app.state.http_error_mapper
        response = mapper.map(exc)
        return JSONResponse(status_code=response.status_code, content=response.payload)


app = create_app()
