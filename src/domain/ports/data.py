"""Data-plane ports: LLM, repositories, embeddings."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.domain.models import (
    MetricExample,
    MetricQuery,
    ThemeExcerpt,
)

if TYPE_CHECKING:
    from src.domain.ports.llm_trace import ILLMCallRecorder
    from src.domain.ports.prompts import IRegenerationPromptBuilder


class ILLMProvider(ABC):
    """Generates and refines poem text using a large language model."""

    @abstractmethod
    def generate(self, prompt: str) -> str: ...

    @abstractmethod
    def regenerate_lines(self, poem: str, feedback: list[str]) -> str: ...


class IProviderInfo(ABC):
    """Exposes metadata about the active LLM provider.

    Kept deliberately tiny so handlers and runners can report which
    provider is wired in without depending on the full `ILLMProvider`
    generation surface.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...


class IRetryPolicy(ABC):
    """Decides whether a failed attempt should be retried and how long to wait.

    Kept as a port so the LLM decorator stack can swap exponential backoff
    for a constant wait, a deadline-based policy, or a fake policy used in
    tests without editing the decorator class itself.
    """

    @abstractmethod
    def should_retry(self, attempt: int, exc: Exception) -> bool:
        """Return True if a new attempt should be made after this failure."""

    @abstractmethod
    def next_delay_sec(self, attempt: int) -> float:
        """Return the delay (in seconds) before the next attempt."""


class ILLMProviderFactory(ABC):
    """Selects an ILLMProvider implementation based on configuration."""

    @abstractmethod
    def create(
        self,
        regeneration_prompt_builder: IRegenerationPromptBuilder,
        recorder: ILLMCallRecorder,
    ) -> ILLMProvider: ...


class IThemeRepository(ABC):
    """Loads theme excerpts from the poetry corpus."""

    @abstractmethod
    def load(self) -> list[ThemeExcerpt]: ...


class IMetricRepository(ABC):
    """Retrieves metrical reference examples."""

    @abstractmethod
    def find(self, query: MetricQuery) -> list[MetricExample]: ...


class IEmbedder(ABC):
    """Encodes text into dense vector representations for semantic search."""

    @abstractmethod
    def encode(self, text: str) -> list[float]: ...
