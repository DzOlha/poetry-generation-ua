"""Service-level fixtures — full PoetryService via composition root."""
from __future__ import annotations

from dataclasses import replace as dc_replace

import pytest

from src.composition_root import build_container, build_poetry_service
from src.config import AppConfig
from src.infrastructure.llm.mock import MockLLMProvider
from src.services.poetry_service import PoetryService


@pytest.fixture(scope="session")
def app_config() -> AppConfig:
    return dc_replace(AppConfig.from_env(), offline_embedder=True)


@pytest.fixture(scope="session")
def poetry_service(mock_llm: MockLLMProvider, app_config: AppConfig) -> PoetryService:
    """Full PoetryService built through the composition root.

    The only override is the LLM: tests inject `MockLLMProvider` so no Gemini
    calls go out. Every other adapter comes from the real container.
    """
    container = build_container(app_config, llm=mock_llm)
    return build_poetry_service(app_config, container=container)
