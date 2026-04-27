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

    def test_validate_exposes_line_displays(self, client: TestClient):
        """An SPA must get per-line char-level stress segments directly."""
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
        data = response.json()
        assert isinstance(data["line_displays"], list)
        assert len(data["line_displays"]) >= 4
        # First non-blank line carries char-level segments.
        first = next(d for d in data["line_displays"] if not d["blank"])
        assert "segments" in first and isinstance(first["segments"], list)
        assert all("ch" in s and "tag" in s for s in first["segments"])
        # At least one segment must have a stress tag.
        tags = {s["tag"] for s in first["segments"]}
        assert tags & {"exp", "act", "both"}

    def test_generate_exposes_extra_metrics_and_iteration_displays(
        self, client: TestClient,
    ):
        payload = {
            "theme": "весна",
            "meter": {"name": "ямб", "foot_count": 4},
            "rhyme": {"pattern": "ABAB"},
            "structure": {"stanza_count": 1, "lines_per_stanza": 4},
            "max_iterations": 1,
        }
        response = client.post("/poems/generate", json=payload)
        data = response.json()
        assert data["theme"] == "весна"
        assert isinstance(data["extra_metrics"], dict)
        assert isinstance(data["validation"]["line_displays"], list)
        # Iteration snapshots expose their own per-iteration line_displays.
        for snap in data["iteration_history"]:
            assert "line_displays" in snap


@pytest.mark.integration
class TestDetectionRouter:
    def test_detect_returns_stanzas_and_line_displays(self, client: TestClient):
        payload = {
            "poem_text": (
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            "detect_meter": True,
            "detect_rhyme": True,
        }
        response = client.post("/poems/detect", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["poem_text"].startswith("Весна прийшла")
        assert data["want_meter"] is True
        assert data["want_rhyme"] is True
        assert isinstance(data["stanzas"], list)
        assert len(data["stanzas"]) >= 1
        stanza = data["stanzas"][0]
        assert "line_displays" in stanza
        assert "lines_count" in stanza

    def test_detect_rejects_non_multiple_of_4(self, client: TestClient):
        payload = {
            "poem_text": "рядок перший достатньо довгий\nрядок другий достатньо довгий\n",
            "detect_meter": True,
            "detect_rhyme": True,
        }
        response = client.post("/poems/detect", json=payload)
        assert response.status_code == 422


@pytest.mark.integration
class TestEvaluationRouter:
    def test_list_scenarios(self, client: TestClient):
        response = client.get("/evaluation/scenarios")
        assert response.status_code == 200
        scenarios = response.json()
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0
        first = scenarios[0]
        assert {"id", "name", "category", "meter", "foot_count", "rhyme_scheme"} <= set(first)

    def test_list_configs(self, client: TestClient):
        response = client.get("/evaluation/configs")
        assert response.status_code == 200
        configs = response.json()
        labels = {c["label"] for c in configs}
        assert "A" in labels and "E" in labels
        assert all("enabled_stages" in c for c in configs)

    def test_run_returns_full_trace(self, client: TestClient):
        payload = {"scenario_id": "N01", "config_label": "A", "max_iterations": 1}
        response = client.post("/evaluation/run", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["scenario"]["id"] == "N01"
        assert data["config"]["label"] == "A"
        trace = data["trace"]
        assert "stages" in trace and isinstance(trace["stages"], list)
        assert "iterations" in trace and isinstance(trace["iterations"], list)
        assert "final_metrics" in trace and isinstance(trace["final_metrics"], dict)
        assert "final_line_displays" in trace

    def test_run_unknown_scenario_returns_404(self, client: TestClient):
        payload = {"scenario_id": "ZZZZZ", "config_label": "A", "max_iterations": 1}
        response = client.post("/evaluation/run", json=payload)
        assert response.status_code == 404


@pytest.mark.integration
class TestSystemRouter:
    def test_llm_info_exposes_provider_model_and_ready_flag(self, client: TestClient):
        # Closes the web↔API parity gap: HTML form pages get LLMInfo through
        # the template context, the SPA had no way to query it. Now it does.
        response = client.get("/system/llm-info")
        assert response.status_code == 200
        data = response.json()
        assert {"provider", "model", "ready", "error"} == set(data)
        # The integration fixture forces llm_provider="mock", so it's ready.
        assert data["provider"] == "mock"
        assert data["ready"] is True


@pytest.mark.integration
class TestEvaluationScenariosByCategory:
    def test_groups_scenarios_into_normal_edge_corner(self, client: TestClient):
        response = client.get("/evaluation/scenarios/by-category")
        assert response.status_code == 200
        data = response.json()
        assert {"normal", "edge", "corner"} == set(data)
        # Each bucket is a list of full scenario records.
        for bucket in data.values():
            assert isinstance(bucket, list)
            for scenario in bucket:
                assert {
                    "id", "name", "category",
                    "theme", "meter", "foot_count", "rhyme_scheme",
                    "stanza_count", "lines_per_stanza",
                } <= set(scenario)
        # Sanity: every scenario tags itself with its bucket's category.
        for category, bucket in data.items():
            for scenario in bucket:
                assert scenario["category"] == category


@pytest.mark.integration
class TestAblationReportEndpoint:
    def test_returns_404_when_no_batch_artifacts_exist(
        self, tmp_path, monkeypatch,
    ) -> None:
        # Build an isolated app pointed at an empty results dir so no batch
        # is found. We can't reuse the module-scoped client because it owns
        # the real `results/` folder which may or may not contain batches.
        cfg = replace(AppConfig.from_env(), offline_embedder=True, llm_provider="mock")
        app = create_app(cfg)
        with TestClient(app) as fresh_client:
            # Override the results_dir on app.state so the dependency picks
            # up the empty tmp_path before the route runs.
            fresh_client.app.state.results_dir = tmp_path  # type: ignore[attr-defined]
            response = fresh_client.get("/evaluation/ablation-report")
        assert response.status_code == 404
        assert "ablation" in response.json()["detail"].lower()


@pytest.mark.integration
class TestLLMReadinessGuard:
    """When no API key is configured and the provider auto-falls-back to
    mock, endpoints that touch the LLM must fail fast with 503 so API
    consumers don't silently receive canned mock poems."""

    @pytest.fixture
    def unconfigured_client(self) -> Generator[TestClient, None, None]:
        # Empty llm_provider + empty api_key → llm_info.ready == False.
        cfg = replace(
            AppConfig.from_env(),
            offline_embedder=True,
            llm_provider="",
            gemini_api_key="",
        )
        app = create_app(cfg)
        with TestClient(app) as ready_client:
            yield ready_client

    def test_generate_blocked_when_key_missing(self, unconfigured_client: TestClient):
        response = unconfigured_client.post("/poems/generate", json={
            "theme": "весна",
            "meter": {"name": "ямб", "foot_count": 4},
            "rhyme": {"pattern": "ABAB"},
            "structure": {"stanza_count": 1, "lines_per_stanza": 4},
            "max_iterations": 1,
        })
        assert response.status_code == 503
        assert "GEMINI_API_KEY" in response.json()["detail"]

    def test_evaluation_blocked_when_key_missing(self, unconfigured_client: TestClient):
        response = unconfigured_client.post("/evaluation/run", json={
            "scenario_id": "N01", "config_label": "A", "max_iterations": 1,
        })
        assert response.status_code == 503
        assert "GEMINI_API_KEY" in response.json()["detail"]

    def test_validate_not_blocked_when_key_missing(self, unconfigured_client: TestClient):
        # Validation doesn't hit the LLM at all, so the guard shouldn't
        # apply — users can still check their own poems without a key.
        response = unconfigured_client.post("/poems/validate", json={
            "poem_text": (
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
            "meter": {"name": "ямб", "foot_count": 4},
            "rhyme": {"pattern": "ABAB"},
        })
        assert response.status_code == 200

    def test_detect_not_blocked_when_key_missing(self, unconfigured_client: TestClient):
        response = unconfigured_client.post("/poems/detect", json={
            "poem_text": (
                "Весна прийшла у ліс зелений,\n"
                "І спів пташок в гіллі бринить.\n"
                "Струмок біжить, мов шлях натхнений,\n"
                "І сонце крізь туман горить.\n"
            ),
        })
        assert response.status_code == 200
