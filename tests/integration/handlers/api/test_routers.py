"""Integration tests for the FastAPI API routers using TestClient.

These tests exercise the HTTP layer end-to-end with a real PoetryService
built around the Mock LLM and the OfflineDeterministicEmbedder so no network
or heavy model downloads are required.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    pytest.skip("fastapi.testclient not installed", allow_module_level=True)

from dataclasses import replace

from src.config import AppConfig
from src.handlers.api.app import create_app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    # Force the offline deterministic embedder via the typed config object
    # rather than mutating os.environ — keeps the fixture self-contained
    # and free of cross-test environment leakage.
    cfg = replace(AppConfig.from_env(), offline_embedder=True, llm_provider="mock")
    app = create_app(cfg)
    # FastAPI's lifespan context manager runs when TestClient enters its
    # `with` block; calling it explicitly here ensures app.state is populated
    # before tests dispatch requests.
    with TestClient(app) as ready_client:
        yield ready_client


@pytest.mark.integration
class TestHealthRouter:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.integration
class TestPoemsRouter:
    def test_generate_success(self, client: TestClient):
        payload = {
            "theme": "весна",
            "meter": {"name": "ямб", "foot_count": 4},
            "rhyme": {"pattern": "ABAB"},
            "structure": {"stanza_count": 1, "lines_per_stanza": 4},
            "max_iterations": 1,
        }
        response = client.post("/poems/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "poem" in data
        assert len(data["poem"]) > 0
        assert "validation" in data
        assert "is_valid" in data["validation"]

    def test_validate_success(self, client: TestClient):
        payload = {
            "poem_text": (
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            "meter": {"name": "ямб", "foot_count": 4},
            "rhyme": {"pattern": "ABAB"},
        }
        response = client.post("/poems/validate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["meter"]["accuracy"], float)
        assert isinstance(data["rhyme"]["accuracy"], float)
        assert isinstance(data["feedback"], list)
