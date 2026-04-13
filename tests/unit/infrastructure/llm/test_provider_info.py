"""Tests for `LLMProviderInfo` and `StaticProviderInfo`."""
from __future__ import annotations

from src.domain.ports import ILLMProvider
from src.infrastructure.llm.provider_info import LLMProviderInfo, StaticProviderInfo


class _AcmeProvider(ILLMProvider):
    def generate(self, prompt: str) -> str:
        return ""

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return ""


class TestLLMProviderInfo:
    def test_name_is_class_name(self) -> None:
        info = LLMProviderInfo(_AcmeProvider())
        assert info.name == "_AcmeProvider"

    def test_name_survives_inner_mutation(self) -> None:
        inner = _AcmeProvider()
        info = LLMProviderInfo(inner)
        # Name is captured at construction so the info object doesn't need
        # to hold a reference to the provider afterwards.
        assert info.name == "_AcmeProvider"


class TestStaticProviderInfo:
    def test_returns_injected_name(self) -> None:
        assert StaticProviderInfo(name="gemini-1.5").name == "gemini-1.5"
