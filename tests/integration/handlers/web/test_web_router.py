"""Integration tests for the web UI routes.

Exercises HTML endpoints end-to-end with a real PoetryService backed by
the Mock LLM and OfflineDeterministicEmbedder — no network required.
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
    cfg = replace(AppConfig.from_env(), offline_embedder=True, llm_provider="mock")
    app = create_app(cfg)
    with TestClient(app) as ready_client:
        yield ready_client


@pytest.mark.integration
class TestIndexPage:
    def test_index_returns_html(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_index_contains_form_elements(self, client: TestClient):
        response = client.get("/")
        body = response.text
        assert "<form" in body.lower() or "generate" in body.lower()


@pytest.mark.integration
class TestGenerateWeb:
    def test_generate_returns_html_with_poem(self, client: TestClient):
        response = client.post("/generate", data={
            "theme": "весна",
            "meter": "ямб",
            "feet": "4",
            "scheme": "ABAB",
            "stanzas": "1",
            "lines": "4",
            "iterations": "1",
        })
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        body = response.text
        # Result page should contain the poem and validation info
        assert "meter" in body.lower() or "ямб" in body

    def test_generate_with_defaults(self, client: TestClient):
        response = client.post("/generate", data={"theme": "зима"})
        assert response.status_code == 200


@pytest.mark.integration
class TestValidateWeb:
    def test_validate_returns_html_with_results(self, client: TestClient):
        response = client.post("/validate-web", data={
            "poem_text": (
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            "meter": "ямб",
            "feet": "4",
            "scheme": "ABAB",
        })
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.integration
class TestEvaluateForm:
    def test_evaluate_form_returns_html(self, client: TestClient):
        response = client.get("/evaluate")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.integration
class TestEvaluateRun:
    def test_evaluate_with_valid_scenario(self, client: TestClient):
        response = client.post("/evaluate", data={
            "scenario_id": "N1",
            "config_label": "A",
            "max_iterations": "1",
        })
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_evaluate_with_unknown_scenario(self, client: TestClient):
        response = client.post("/evaluate", data={
            "scenario_id": "ZZZZZ",
            "config_label": "A",
            "max_iterations": "1",
        })
        assert response.status_code == 200
        body = response.text
        assert "Unknown scenario ID" in body or "ZZZZZ" in body


@pytest.mark.integration
class TestWebReadinessGuard:
    """With no API key and auto-provider, the web generate/evaluate forms
    must refuse to run the pipeline and render an error page instead —
    mirroring the JSON API's 503 guard so a direct form POST can't bypass
    the disabled-button UI."""

    @pytest.fixture(scope="class")
    def unconfigured_client(self) -> Generator[TestClient, None, None]:
        cfg = replace(
            AppConfig.from_env(),
            offline_embedder=True,
            llm_provider="",
            gemini_api_key="",
        )
        app = create_app(cfg)
        with TestClient(app) as ready_client:
            yield ready_client

    def test_generate_form_shows_error_banner_when_key_missing(
        self, unconfigured_client: TestClient,
    ):
        response = unconfigured_client.get("/generate")
        assert response.status_code == 200
        body = response.text
        # Banner text + disabled-button marker appear only when
        # llm_info.ready is False.
        assert "GEMINI_API_KEY" in body
        assert 'aria-disabled="true"' in body

    def test_generate_post_blocks_pipeline_when_key_missing(
        self, unconfigured_client: TestClient,
    ):
        response = unconfigured_client.post("/generate", data={
            "theme": "весна", "meter": "ямб", "feet": "4",
            "scheme": "ABAB", "stanzas": "1", "iterations": "1",
        })
        # Handler rendered error.html instead of calling the pipeline —
        # status stays 200 but body reflects the refusal.
        assert response.status_code == 200
        assert "GEMINI_API_KEY" in response.text

    def test_evaluate_form_shows_error_banner_when_key_missing(
        self, unconfigured_client: TestClient,
    ):
        response = unconfigured_client.get("/evaluate")
        assert response.status_code == 200
        assert "GEMINI_API_KEY" in response.text
        assert 'aria-disabled="true"' in response.text

    def test_evaluate_post_blocks_pipeline_when_key_missing(
        self, unconfigured_client: TestClient,
    ):
        response = unconfigured_client.post("/evaluate", data={
            "scenario_id": "N01", "config_label": "A", "max_iterations": "1",
        })
        assert response.status_code == 200
        assert "GEMINI_API_KEY" in response.text
