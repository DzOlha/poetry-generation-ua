"""Tests for the route-aware RequestValidationError handler."""
from __future__ import annotations

from collections.abc import Generator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from src.config import AppConfig
from src.handlers.api.app import create_app
from src.handlers.web.validation_handler import (
    _FIELD_LABELS,
    _HTML_POST_PATHS,
    _field_label,
    _translate,
)


@pytest.fixture(scope="module")
def web_app_client() -> Generator[TestClient, None, None]:
    # Use mock LLM + offline embedder so the lifespan setup is fast and
    # the test does not require GEMINI_API_KEY / network.
    cfg = replace(AppConfig.from_env(), offline_embedder=True, llm_provider="mock")
    app = create_app(cfg)
    with TestClient(app) as client:
        yield client


class TestFieldLabel:
    def test_known_field_translated(self):
        assert _field_label(("body", "feet")) == _FIELD_LABELS["feet"]

    def test_unknown_field_returned_as_is(self):
        assert _field_label(("body", "unknown_field")) == "unknown_field"

    def test_skips_loc_metadata_tokens(self):
        # ["body", "structure", "stanza_count"] → "stanza_count" wins.
        assert _field_label(("body", "structure", "stanza_count")) == "Кількість строф"

    def test_empty_loc_returns_default(self):
        assert _field_label(()) == "поле"


class TestTranslate:
    def test_less_than_equal_uses_le_value(self):
        msg = _translate({"type": "less_than_equal", "ctx": {"le": 6}})
        assert "не більше за 6" in msg

    def test_string_too_long_uses_max_length(self):
        msg = _translate({"type": "string_too_long", "ctx": {"max_length": 200}})
        assert "200 символів" in msg

    def test_string_too_short_message(self):
        msg = _translate({"type": "string_too_short", "ctx": {"min_length": 1}})
        assert "не може бути порожнім" in msg

    def test_missing_field_message(self):
        msg = _translate({"type": "missing"})
        assert "обов'язков" in msg

    def test_unknown_type_falls_back_to_msg(self):
        msg = _translate({"type": "unknown_kind", "msg": "Original FastAPI message"})
        assert msg == "Original FastAPI message"


class TestHtmlPostPaths:
    def test_known_html_routes_present(self):
        # If new HTML POST endpoints are added, they need to be added here
        # too — otherwise validation errors leak as JSON to browser users.
        assert "/generate" in _HTML_POST_PATHS
        assert "/validate-web" in _HTML_POST_PATHS
        assert "/detect" in _HTML_POST_PATHS
        assert "/evaluate" in _HTML_POST_PATHS

    def test_api_routes_not_in_set(self):
        # Sanity: no `/poems/...` or `/evaluation/...` API path slipped in.
        for p in _HTML_POST_PATHS:
            assert not p.startswith("/poems")
            assert not p.startswith("/evaluation/")
            assert not p.startswith("/system")


class TestEndToEndRouting:
    """Smoke-test that JSON API still gets JSON, web POST gets HTML."""

    def test_api_validation_error_returns_json(self, web_app_client):
        r = web_app_client.post("/poems/validate", json={
            "poem_text": "x", "meter": {"foot_count": 99},
        })
        assert r.status_code == 422
        assert r.headers["content-type"].startswith("application/json")
        body = r.json()
        assert "detail" in body

    def test_web_form_validation_error_renders_html(self, web_app_client):
        r = web_app_client.post("/generate", data={
            "theme": "весна", "meter": "ямб", "feet": 99,
            "scheme": "ABAB", "stanzas": 1, "iterations": 1,
        })
        assert r.status_code == 422
        assert r.headers["content-type"].startswith("text/html")
        # User-facing Ukrainian message present + field label translated.
        assert "Введені дані не пройшли перевірку" in r.text
        assert "Кількість стоп" in r.text
        assert "не більше за 6" in r.text

    def test_web_empty_theme_renders_html_with_field_name(self, web_app_client):
        r = web_app_client.post("/generate", data={
            "theme": "", "meter": "ямб", "feet": 4,
            "scheme": "ABAB", "stanzas": 1, "iterations": 1,
        })
        assert r.status_code == 422
        assert r.headers["content-type"].startswith("text/html")
        assert "Тема" in r.text
        # Jinja2 HTML-escapes the apostrophe in «обов'язков», so we check
        # the prefix without it (or the alt phrase).
        assert "обов" in r.text or "не може бути порожнім" in r.text
