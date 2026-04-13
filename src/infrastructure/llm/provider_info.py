"""`IProviderInfo` implementations.

Adapters that let non-LLM consumers (handlers, runners, tests) learn the
class name of the active `ILLMProvider` without depending on the provider
itself. The composition root wraps each provider in `LLMProviderInfo` and
hands the narrow port to `PoetryService` so the service stops importing
`ILLMProvider` just to read `type(llm).__name__`.
"""
from __future__ import annotations

from src.domain.ports import ILLMProvider, IProviderInfo


class LLMProviderInfo(IProviderInfo):
    """Exposes the class name of the injected `ILLMProvider`."""

    def __init__(self, provider: ILLMProvider) -> None:
        self._name: str = type(provider).__name__

    @property
    def name(self) -> str:
        return self._name


class StaticProviderInfo(IProviderInfo):
    """`IProviderInfo` with a fixed name — convenient for tests and reports."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name
