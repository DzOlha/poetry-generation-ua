"""Tests for the quota-error parsing helpers in gemini.py.

Pinned against the actual Gemini 429 payload format so the user-facing
message stays informative when google-genai changes its rendering.
"""
from __future__ import annotations

from src.infrastructure.llm.gemini import (
    _build_quota_message,
    _is_quota_error,
)

_REAL_GEMINI_429 = (
    "Gemini call failed: 429 RESOURCE_EXHAUSTED. "
    "{'error': {'code': 429, 'message': 'You exceeded your current quota, "
    "please check your plan and billing details. ... \\n* Quota exceeded for "
    "metric: generativelanguage.googleapis.com/generate_requests_per_model_per_day, "
    "limit: 250, model: gemini-3.1-pro\\nPlease retry in 22h18m29.296643517s.', "
    "'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': "
    "'type.googleapis.com/google.rpc.QuotaFailure', 'violations': "
    "[{'quotaValue': '250'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', "
    "'retryDelay': '80309s'}]}}"
)


class TestIsQuotaError:
    def test_detects_resource_exhausted(self) -> None:
        assert _is_quota_error(Exception(_REAL_GEMINI_429)) is True

    def test_detects_lowercase_quota_exceeded(self) -> None:
        assert _is_quota_error(Exception("quota exceeded for project foo")) is True

    def test_ignores_unrelated_errors(self) -> None:
        assert _is_quota_error(Exception("Network read timeout after 5s")) is False
        assert _is_quota_error(Exception("Invalid API key")) is False


class TestBuildQuotaMessage:
    def test_extracts_limit_and_human_retry_hint(self) -> None:
        msg = _build_quota_message(_REAL_GEMINI_429)
        assert "250 запитів" in msg
        # 22h18m → "приблизно через 22 год"
        assert "22 год" in msg
        assert "Спробуйте, будь ласка" in msg

    def test_extracts_limit_when_only_quota_value_present(self) -> None:
        raw = "Some prefix 'quotaValue': '100' suffix"
        msg = _build_quota_message(raw)
        assert "100 запитів" in msg

    def test_falls_back_to_generic_when_limit_not_found(self) -> None:
        msg = _build_quota_message("Quota exceeded with no number anywhere")
        assert "ліміту запитів" in msg
        # No explicit limit number leaked into the user message.
        assert "0" not in msg

    def test_uses_seconds_retry_hint_when_human_form_missing(self) -> None:
        raw = "Quota exceeded. 'retryDelay': '7200s'"
        msg = _build_quota_message(raw)
        # 7200s → "приблизно через 2 год"
        assert "2 год" in msg

    def test_falls_back_to_pizniше_when_no_retry_hint(self) -> None:
        raw = "Quota exceeded with limit: 50 and no retry hint"
        msg = _build_quota_message(raw)
        assert "50 запитів" in msg
        assert "пізніше" in msg
