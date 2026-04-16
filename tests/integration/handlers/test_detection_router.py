"""Integration test: detection API endpoint."""
from __future__ import annotations

from collections.abc import Generator

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    pytest.skip("fastapi.testclient not installed", allow_module_level=True)

from src.config import AppConfig, DetectionConfig
from src.handlers.api.app import create_app


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    config = AppConfig(
        offline_embedder=True,
        detection=DetectionConfig(
            meter_min_accuracy=0.70,
            rhyme_min_accuracy=0.50,
        ),
    )
    app = create_app(config)
    with TestClient(app) as ready_client:
        yield ready_client


class TestDetectionRouter:
    @pytest.mark.integration
    def test_detect_endpoint_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/poems/detect",
            json={
                "poem_text": (
                    "Реве та стогне Дніпр широкий\n"
                    "Сердитий вітер завива\n"
                    "Додолу верби гне високі\n"
                    "Горами хвилю підійма"
                ),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "meter" in data
        assert "rhyme" in data
        assert "is_detected" in data

    @pytest.mark.integration
    def test_detect_with_sample_lines(self, client: TestClient) -> None:
        response = client.post(
            "/poems/detect",
            json={
                "poem_text": (
                    "Рядок один\nРядок два\nРядок три\nРядок чотири"
                ),
                "sample_lines": 4,
            },
        )
        assert response.status_code == 200

    @pytest.mark.integration
    def test_detect_empty_text_returns_422(self, client: TestClient) -> None:
        response = client.post("/poems/detect", json={"poem_text": ""})
        assert response.status_code == 422
