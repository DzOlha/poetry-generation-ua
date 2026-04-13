"""Tests for the registry-based `DefaultLLMProviderFactory`."""
from __future__ import annotations

from dataclasses import replace

import pytest

from src.config import AppConfig
from src.domain.errors import ConfigurationError
from src.domain.ports import ILLMProvider, IRegenerationPromptBuilder
from src.infrastructure.llm.factory import DefaultLLMProviderFactory
from src.infrastructure.llm.gemini import GeminiProvider
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder


def _builder() -> IRegenerationPromptBuilder:
    return NumberedLinesRegenerationPromptBuilder()


class _FakeProvider(ILLMProvider):
    def __init__(self, label: str) -> None:
        self.label = label

    def generate(self, prompt: str) -> str:
        return self.label

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return self.label


class TestDefaultLLMProviderFactory:
    def test_auto_selects_mock_when_no_api_key(self) -> None:
        cfg = replace(AppConfig.from_env(), gemini_api_key="", llm_provider="")
        factory = DefaultLLMProviderFactory(config=cfg)
        assert isinstance(factory.create(_builder()), MockLLMProvider)

    def test_explicit_mock_selection(self) -> None:
        cfg = replace(
            AppConfig.from_env(),
            gemini_api_key="present",
            llm_provider="mock",
        )
        factory = DefaultLLMProviderFactory(config=cfg)
        assert isinstance(factory.create(_builder()), MockLLMProvider)

    def test_unknown_provider_raises_configuration_error(self) -> None:
        cfg = replace(AppConfig.from_env(), llm_provider="mock")
        # Bypass frozen config validation by setting provider after construction
        object.__setattr__(cfg, "llm_provider", "nonexistent")
        factory = DefaultLLMProviderFactory(config=cfg)
        with pytest.raises(ConfigurationError, match="Unknown LLM provider"):
            factory.create(_builder())

    def test_register_adds_new_provider(self) -> None:
        cfg = replace(AppConfig.from_env(), llm_provider="mock")
        # Bypass frozen config validation to test dynamic registration
        object.__setattr__(cfg, "llm_provider", "fake")
        factory = DefaultLLMProviderFactory(config=cfg)
        factory.register(
            "fake",
            lambda _cfg, _b: _FakeProvider(label="labelled"),
        )
        provider = factory.create(_builder())
        assert isinstance(provider, _FakeProvider)
        assert provider.label == "labelled"

    def test_auto_selects_gemini_when_api_key_set(self) -> None:
        # We can't actually instantiate GeminiProvider without a real SDK, so
        # verify via the registry: replace the gemini entry with a sentinel
        # and check that "gemini" is the resolved name.
        cfg = replace(
            AppConfig.from_env(), gemini_api_key="present", llm_provider="",
        )
        factory = DefaultLLMProviderFactory(
            config=cfg,
            builders={
                "gemini": lambda _c, _b: _FakeProvider(label="gemini"),
                "mock": lambda _c, _b: _FakeProvider(label="mock"),
            },
        )
        provider = factory.create(_builder())
        assert isinstance(provider, _FakeProvider)
        assert provider.label == "gemini"

    def test_unused_gemini_builder_reference(self) -> None:
        # Sanity check that the imported GeminiProvider symbol still resolves;
        # guards against accidental deletion of the import when refactoring.
        assert GeminiProvider is not None
