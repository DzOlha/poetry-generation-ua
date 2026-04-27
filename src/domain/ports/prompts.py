"""Prompt building and regeneration ports."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models import (
    GenerationRequest,
    MetricExample,
    RetrievedExcerpt,
)
from src.domain.models.feedback import LineFeedback, PairFeedback


class IPromptBuilder(ABC):
    """Constructs LLM prompts for poetry generation."""

    @abstractmethod
    def build(
        self,
        request: GenerationRequest,
        retrieved: list[RetrievedExcerpt],
        examples: list[MetricExample],
    ) -> str: ...


class IRegenerationPromptBuilder(ABC):
    """Builds the refinement prompt used by ILLMProvider.regenerate_lines."""

    @abstractmethod
    def build(self, poem: str, feedback_messages: list[str]) -> str: ...


class IRegenerationMerger(ABC):
    """Merges regenerated output back into the original poem."""

    @abstractmethod
    def merge(
        self,
        original: str,
        regenerated: str,
        meter_feedback: tuple[LineFeedback, ...],
        rhyme_feedback: tuple[PairFeedback, ...],
    ) -> str: ...


class IFeedbackFormatter(ABC):
    """Renders structured LineFeedback / PairFeedback into natural-language strings."""

    @abstractmethod
    def format_line(self, fb: LineFeedback) -> str: ...

    @abstractmethod
    def format_pair(self, fb: PairFeedback) -> str: ...
