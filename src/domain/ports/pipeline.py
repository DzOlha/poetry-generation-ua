"""Pipeline orchestration ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    MeterResult,
    MeterSpec,
    RhymeResult,
    RhymeScheme,
)

if TYPE_CHECKING:
    from src.domain.evaluation import IterationRecord
    from src.domain.pipeline_context import PipelineState


class IPipelineStage(ABC):
    """One stage of the generation / evaluation pipeline."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, state: PipelineState) -> None: ...


class IStageSkipPolicy(ABC):
    """Decides whether a stage should be skipped before it runs."""

    @abstractmethod
    def should_skip(self, state: PipelineState, stage_name: str) -> bool: ...


class IStageFactory(ABC):
    """Produces the ordered list of `IPipelineStage` to run for a given config."""

    @abstractmethod
    def build_for(self, enabled_stages: frozenset[str]) -> list[IPipelineStage]: ...


class IPipeline(ABC):
    """Runs an ordered sequence of pipeline stages over a PipelineState."""

    @abstractmethod
    def run(self, state: PipelineState) -> None: ...


class IIterationStopPolicy(ABC):
    """Decides whether the regeneration feedback loop should stop."""

    @abstractmethod
    def should_stop(
        self,
        iteration: int,
        max_iterations: int,
        meter_result: MeterResult,
        rhyme_result: RhymeResult,
        history: tuple[IterationRecord, ...],
    ) -> bool: ...


@dataclass(frozen=True)
class FeedbackCycleOutcome:
    """Bundle produced by one `IFeedbackCycle.run()` call."""

    meter: MeterResult
    rhyme: RhymeResult
    feedback_messages: tuple[str, ...]


class IFeedbackCycle(ABC):
    """One validate -> format round over a poem."""

    @abstractmethod
    def run(
        self,
        poem_text: str,
        meter: MeterSpec,
        rhyme: RhymeScheme,
    ) -> FeedbackCycleOutcome: ...


class IFeedbackIterator(ABC):
    """Encapsulates the regenerate -> validate iteration loop."""

    @abstractmethod
    def iterate(self, state: PipelineState) -> None: ...


class IPoemGenerationPipeline(ABC):
    """Top-level use-case for generating a poem from a domain request."""

    @abstractmethod
    def build(self, request: GenerationRequest) -> GenerationResult: ...
