"""Generation sub-container — façade composing three focused sub-containers.

The original module bundled five concerns (data plane, LLM stack, prompt
builders, feedback loop, pipeline stages). After the architectural audit
those concerns now live in their own modules:

  - ``generation_data_plane``      — repositories, embedder, retriever
  - ``generation_llm_stack``       — LLM factory + reliability decorators
  - ``generation_pipeline_stages`` — prompts, feedback loop, pipeline

This file exists only to preserve the original public API
(``GenerationSubContainer``) so the parent ``Container`` and any
existing call sites do not have to change. Every accessor delegates to
the matching focused sub-container; nothing else lives here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import (
    IEmbedder,
    IFeedbackCycle,
    IFeedbackIterator,
    IIterationStopPolicy,
    ILLMCallRecorder,
    ILLMProvider,
    ILLMProviderFactory,
    IMetricRepository,
    IPipeline,
    IPoemExtractor,
    IPoemGenerationPipeline,
    IPoemOutputSanitizer,
    IPromptBuilder,
    IProviderInfo,
    IRegenerationMerger,
    IRegenerationPromptBuilder,
    IRetriever,
    IStageFactory,
    IStageSkipPolicy,
    IThemeRepository,
)
from src.infrastructure.composition.generation_data_plane import (
    GenerationDataPlaneSubContainer,
)
from src.infrastructure.composition.generation_llm_stack import LLMStackSubContainer
from src.infrastructure.composition.generation_pipeline_stages import (
    PipelineStagesSubContainer,
)
from src.infrastructure.pipeline import StageRegistration

if TYPE_CHECKING:
    from src.composition_root import Container


class GenerationSubContainer:
    """Thin façade — three focused sub-containers over the shared cache."""

    _stages: PipelineStagesSubContainer

    def __init__(self, parent: Container) -> None:
        self._parent = parent
        self._data_plane = GenerationDataPlaneSubContainer(parent)
        # The LLM stack needs the regeneration prompt builder lazily —
        # the pipeline-stages container owns it. Pass a callable so the
        # cycle stays untriggered until the LLM is actually constructed.
        self._llm_stack = LLMStackSubContainer(
            parent=parent,
            regeneration_prompt_builder_factory=self._regen_prompt_builder,
        )
        self._stages = PipelineStagesSubContainer(
            parent=parent,
            data_plane=self._data_plane,
            llm_stack=self._llm_stack,
        )

    def _regen_prompt_builder(self) -> IRegenerationPromptBuilder:
        return self._stages.regeneration_prompt_builder()

    # ------------------------------------------------------------------
    # Data plane delegation
    # ------------------------------------------------------------------

    def theme_repo(self) -> IThemeRepository:
        return self._data_plane.theme_repo()

    def metric_repo(self) -> IMetricRepository:
        return self._data_plane.metric_repo()

    def embedder(self) -> IEmbedder:
        return self._data_plane.embedder()

    def retriever(self) -> IRetriever:
        return self._data_plane.retriever()

    # ------------------------------------------------------------------
    # LLM stack delegation
    # ------------------------------------------------------------------

    def llm_factory(self) -> ILLMProviderFactory:
        return self._llm_stack.llm_factory()

    def poem_output_sanitizer(self) -> IPoemOutputSanitizer:
        return self._llm_stack.poem_output_sanitizer()

    def poem_extractor(self) -> IPoemExtractor:
        return self._llm_stack.poem_extractor()

    def llm_call_recorder(self) -> ILLMCallRecorder:
        return self._llm_stack.llm_call_recorder()

    def llm(self) -> ILLMProvider:
        return self._llm_stack.llm()

    def provider_info(self) -> IProviderInfo:
        return self._llm_stack.provider_info()

    # ------------------------------------------------------------------
    # Pipeline-stages delegation
    # ------------------------------------------------------------------

    def regeneration_prompt_builder(self) -> IRegenerationPromptBuilder:
        return self._stages.regeneration_prompt_builder()

    def prompt_builder(self) -> IPromptBuilder:
        return self._stages.prompt_builder()

    def regeneration_merger(self) -> IRegenerationMerger:
        return self._stages.regeneration_merger()

    def iteration_stop_policy(self) -> IIterationStopPolicy:
        return self._stages.iteration_stop_policy()

    def feedback_cycle(self) -> IFeedbackCycle:
        return self._stages.feedback_cycle()

    def feedback_iterator(self) -> IFeedbackIterator:
        return self._stages.feedback_iterator()

    def skip_policy(self) -> IStageSkipPolicy:
        return self._stages.skip_policy()

    def stage_registrations(self) -> list[StageRegistration]:
        return self._stages.stage_registrations()

    def stage_factory(self) -> IStageFactory:
        return self._stages.stage_factory()

    def generation_pipeline_inner(self) -> IPipeline:
        return self._stages.generation_pipeline_inner()

    def poem_generation_pipeline(self) -> IPoemGenerationPipeline:
        return self._stages.poem_generation_pipeline()
