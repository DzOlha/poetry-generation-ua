"""Contract every `ILLMProvider` implementation must satisfy.

Concrete test modules subclass `ILLMProviderContract` and override
`_make_provider` to return the implementation under test. The contract
covers the behavioural guarantees callers rely on — the decorator stack
in particular has to keep these intact, so it inherits from the contract
too.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ports import ILLMProvider


class ILLMProviderContract(ABC):
    """Every ILLMProvider must satisfy these behavioural guarantees."""

    @abstractmethod
    def _make_provider(self) -> ILLMProvider:
        """Return a fresh provider under test."""

    def test_generate_returns_non_empty_string(self) -> None:
        provider = self._make_provider()
        result = provider.generate("тема весна")
        assert isinstance(result, str)
        assert result, "generate() must return a non-empty string"

    def test_regenerate_returns_non_empty_string(self) -> None:
        provider = self._make_provider()
        poem = "рядок один\nрядок два\nрядок три\nрядок чотири\n"
        result = provider.regenerate_lines(poem, ["fix line 1"])
        assert isinstance(result, str)
        assert result, "regenerate_lines() must return a non-empty string"

    def test_regenerate_with_empty_feedback_accepted(self) -> None:
        """An empty feedback list is a valid no-op regeneration request."""
        provider = self._make_provider()
        poem = "рядок один\nрядок два\nрядок три\nрядок чотири\n"
        result = provider.regenerate_lines(poem, [])
        assert isinstance(result, str)

    def test_generate_empty_prompt_returns_string(self) -> None:
        """An empty prompt must not crash — providers should handle gracefully."""
        provider = self._make_provider()
        result = provider.generate("")
        assert isinstance(result, str)
