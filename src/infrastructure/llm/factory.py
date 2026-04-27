"""`DefaultLLMProviderFactory` — registry-based provider selection.

Previously used an inline `if api_key: GeminiProvider else MockLLMProvider`
branch. The audit flagged this as an OCP violation: adding a new provider
(Claude, OpenAI, local Ollama) required editing the factory.

The factory now holds a `{name: builder}` registry. Selection happens by
name (taken from `AppConfig.llm_provider`, defaulting to `"auto"`), and
builders are pure factory functions that receive the config and return a
ready `ILLMProvider`. Adding a new provider = one new entry in
`_DEFAULT_BUILDERS` in the composition root (or a `register()` call).
"""
from __future__ import annotations

from collections.abc import Callable

from src.config import AppConfig
from src.domain.errors import ConfigurationError
from src.domain.ports import (
    ILLMCallRecorder,
    ILLMProvider,
    ILLMProviderFactory,
    IRegenerationPromptBuilder,
)
from src.infrastructure.llm.gemini import GeminiProvider
from src.infrastructure.llm.mock import MockLLMProvider

ProviderBuilder = Callable[
    [AppConfig, IRegenerationPromptBuilder, ILLMCallRecorder],
    ILLMProvider,
]


def build_gemini_provider(
    config: AppConfig,
    regeneration_prompt_builder: IRegenerationPromptBuilder,
    recorder: ILLMCallRecorder,
) -> ILLMProvider:
    """Default Gemini builder used by `DefaultLLMProviderFactory`."""
    return GeminiProvider(
        api_key=config.gemini_api_key,
        regeneration_prompt_builder=regeneration_prompt_builder,
        recorder=recorder,
        model=config.gemini_model,
        temperature=config.gemini_temperature,
        max_output_tokens=config.gemini_max_tokens,
        disable_thinking=config.gemini_disable_thinking,
    )


def build_mock_provider(
    config: AppConfig,
    regeneration_prompt_builder: IRegenerationPromptBuilder,
    recorder: ILLMCallRecorder,
) -> ILLMProvider:
    """Default mock builder used by `DefaultLLMProviderFactory`."""
    del config, recorder
    return MockLLMProvider(regeneration_prompt_builder=regeneration_prompt_builder)


_DEFAULT_BUILDERS: dict[str, ProviderBuilder] = {
    "gemini": build_gemini_provider,
    "mock": build_mock_provider,
}


class DefaultLLMProviderFactory(ILLMProviderFactory):
    """`ILLMProviderFactory` that dispatches to a `{name: builder}` registry.

    Selection rules:
      1. If `config.llm_provider` is a non-empty string, use that entry.
      2. Otherwise, fall back to auto-selection: Gemini when an API key is
         present, mock otherwise.

    Callers can extend the factory with `register()` without subclassing.
    """

    def __init__(
        self,
        config: AppConfig,
        builders: dict[str, ProviderBuilder] | None = None,
    ) -> None:
        self._config = config
        # Copy so callers cannot mutate `_DEFAULT_BUILDERS` by accident.
        self._builders: dict[str, ProviderBuilder] = dict(
            builders if builders is not None else _DEFAULT_BUILDERS,
        )

    def register(self, name: str, builder: ProviderBuilder) -> None:
        """Register a new provider builder (overrides any existing entry)."""
        self._builders[name] = builder

    def create(
        self,
        regeneration_prompt_builder: IRegenerationPromptBuilder,
        recorder: ILLMCallRecorder,
    ) -> ILLMProvider:
        cfg = self._config
        provider_name = self._resolve_name(cfg)
        try:
            builder = self._builders[provider_name]
        except KeyError as exc:
            available = sorted(self._builders)
            raise ConfigurationError(
                f"Unknown LLM provider {provider_name!r}; available: {available}",
            ) from exc
        return builder(cfg, regeneration_prompt_builder, recorder)

    @staticmethod
    def _resolve_name(cfg: AppConfig) -> str:
        explicit = getattr(cfg, "llm_provider", "") or ""
        if explicit:
            return explicit
        return "gemini" if cfg.gemini_api_key else "mock"
