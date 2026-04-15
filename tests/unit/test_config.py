"""Tests for configuration validation logic in src.config."""
from __future__ import annotations

import pytest

from src.config import AppConfig, DetectionConfig, LLMReliabilityConfig, ValidationConfig
from src.domain.errors import ConfigurationError


class TestValidationConfig:
    def test_defaults_are_valid(self):
        vc = ValidationConfig()
        assert vc.rhyme_threshold == 0.55

    @pytest.mark.parametrize("value", [-0.1, 1.1, 2.0])
    def test_rhyme_threshold_out_of_range(self, value):
        with pytest.raises(ConfigurationError, match="rhyme_threshold"):
            ValidationConfig(rhyme_threshold=value)

    @pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
    def test_rhyme_threshold_boundary_values(self, value):
        vc = ValidationConfig(rhyme_threshold=value)
        assert vc.rhyme_threshold == value

    def test_meter_allowed_mismatches_negative(self):
        with pytest.raises(ConfigurationError, match="meter_allowed_mismatches"):
            ValidationConfig(meter_allowed_mismatches=-1)

    def test_meter_allowed_mismatches_zero_is_valid(self):
        vc = ValidationConfig(meter_allowed_mismatches=0)
        assert vc.meter_allowed_mismatches == 0

    @pytest.mark.parametrize("value", [-0.1, 1.1])
    def test_bsp_score_threshold_out_of_range(self, value):
        with pytest.raises(ConfigurationError, match="bsp_score_threshold"):
            ValidationConfig(bsp_score_threshold=value)

    @pytest.mark.parametrize("value", [0.0, 1.0])
    def test_bsp_score_threshold_boundary_values(self, value):
        vc = ValidationConfig(bsp_score_threshold=value)
        assert vc.bsp_score_threshold == value

    def test_frozen(self):
        vc = ValidationConfig()
        with pytest.raises(AttributeError):
            vc.rhyme_threshold = 0.5  # type: ignore[misc]


class TestDetectionConfig:
    def test_defaults_are_valid(self):
        dc = DetectionConfig()
        assert dc.meter_min_accuracy == 0.85
        assert dc.rhyme_min_accuracy == 0.5
        assert dc.sample_lines == 4

    @pytest.mark.parametrize("value", [-0.1, 1.1])
    def test_meter_min_accuracy_out_of_range(self, value):
        with pytest.raises(ConfigurationError, match="meter_min_accuracy"):
            DetectionConfig(meter_min_accuracy=value)

    @pytest.mark.parametrize("value", [-0.1, 1.1])
    def test_rhyme_min_accuracy_out_of_range(self, value):
        with pytest.raises(ConfigurationError, match="rhyme_min_accuracy"):
            DetectionConfig(rhyme_min_accuracy=value)

    def test_rhyme_min_accuracy_default_tolerates_single_slant_pair(self):
        # Regression guard: a four-line sample yields only two rhyme pairs,
        # so the aggregate accuracy resolves to 0.0 / 0.5 / 1.0. The default
        # must admit 0.5 — a single solid rhyme is enough signal for the
        # scheme; requiring 0.75 would silently demand both pairs be exact.
        assert DetectionConfig().rhyme_min_accuracy <= 0.5

    def test_sample_lines_too_small(self):
        with pytest.raises(ConfigurationError, match="sample_lines"):
            DetectionConfig(sample_lines=1)

    def test_feet_range_invalid(self):
        with pytest.raises(ConfigurationError, match="feet_min"):
            DetectionConfig(feet_min=5, feet_max=3)

    def test_frozen(self):
        dc = DetectionConfig()
        with pytest.raises(AttributeError):
            dc.sample_lines = 8  # type: ignore[misc]


class TestLLMReliabilityConfig:
    def test_defaults_are_valid(self):
        rc = LLMReliabilityConfig()
        assert rc.timeout_sec == 60.0
        assert rc.retry_max_attempts == 3

    @pytest.mark.parametrize("value", [0.0, -1.0, -100.0])
    def test_timeout_sec_must_be_positive(self, value):
        with pytest.raises(ConfigurationError, match="timeout_sec"):
            LLMReliabilityConfig(timeout_sec=value)

    def test_timeout_sec_small_positive_is_valid(self):
        rc = LLMReliabilityConfig(timeout_sec=0.001)
        assert rc.timeout_sec == 0.001

    @pytest.mark.parametrize("value", [0, -1])
    def test_retry_max_attempts_must_be_at_least_one(self, value):
        with pytest.raises(ConfigurationError, match="retry_max_attempts"):
            LLMReliabilityConfig(retry_max_attempts=value)

    def test_retry_max_attempts_one_is_valid(self):
        rc = LLMReliabilityConfig(retry_max_attempts=1)
        assert rc.retry_max_attempts == 1

    def test_frozen(self):
        rc = LLMReliabilityConfig()
        with pytest.raises(AttributeError):
            rc.timeout_sec = 10.0  # type: ignore[misc]


class TestAppConfig:
    def test_defaults_are_valid(self):
        cfg = AppConfig()
        assert cfg.port == 8000
        assert cfg.gemini_temperature == 0.9

    @pytest.mark.parametrize("provider", ["", "gemini", "mock"])
    def test_known_llm_providers_accepted(self, provider):
        cfg = AppConfig(llm_provider=provider)
        assert cfg.llm_provider == provider

    def test_unknown_llm_provider_rejected(self):
        with pytest.raises(ConfigurationError, match="Unknown llm_provider"):
            AppConfig(llm_provider="openai")

    @pytest.mark.parametrize("value", [-0.1, 2.1, 5.0])
    def test_gemini_temperature_out_of_range(self, value):
        with pytest.raises(ConfigurationError, match="gemini_temperature"):
            AppConfig(gemini_temperature=value)

    @pytest.mark.parametrize("value", [0.0, 1.0, 2.0])
    def test_gemini_temperature_boundary_values(self, value):
        cfg = AppConfig(gemini_temperature=value)
        assert cfg.gemini_temperature == value

    @pytest.mark.parametrize("value", [0, -1, -100])
    def test_gemini_max_tokens_must_be_positive(self, value):
        with pytest.raises(ConfigurationError, match="gemini_max_tokens"):
            AppConfig(gemini_max_tokens=value)

    def test_gemini_max_tokens_one_is_valid(self):
        cfg = AppConfig(gemini_max_tokens=1)
        assert cfg.gemini_max_tokens == 1

    @pytest.mark.parametrize("value", [0, -1, 65536, 99999])
    def test_port_out_of_range(self, value):
        with pytest.raises(ConfigurationError, match="port"):
            AppConfig(port=value)

    @pytest.mark.parametrize("value", [1, 8080, 65535])
    def test_port_boundary_values(self, value):
        cfg = AppConfig(port=value)
        assert cfg.port == value

    def test_frozen(self):
        cfg = AppConfig()
        with pytest.raises(AttributeError):
            cfg.port = 9000  # type: ignore[misc]

    def test_from_env_uses_defaults(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("PORT", raising=False)
        cfg = AppConfig.from_env()
        assert cfg.port == 8000
        assert cfg.gemini_api_key == ""

    def test_from_env_reads_overrides(self, monkeypatch):
        monkeypatch.setenv("PORT", "9090")
        monkeypatch.setenv("GEMINI_TEMPERATURE", "1.5")
        monkeypatch.setenv("DEBUG", "true")
        cfg = AppConfig.from_env()
        assert cfg.port == 9090
        assert cfg.gemini_temperature == 1.5
        assert cfg.debug is True
