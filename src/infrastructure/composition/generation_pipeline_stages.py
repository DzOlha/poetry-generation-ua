"""Pipeline-stage composition — registrations + factory + pipeline.

Split out from ``generation.py`` so the stage list and pipeline-builder
plumbing live in one place. Adding a new pipeline stage now means
editing one focused module instead of the broader generation container.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.evaluation import (
    STAGE_FEEDBACK_LOOP,
    STAGE_INITIAL_GENERATION,
    STAGE_METRIC_EXAMPLES,
    STAGE_PROMPT_CONSTRUCTION,
    STAGE_RETRIEVAL,
    STAGE_VALIDATION,
)
from src.domain.ports import (
    IFeedbackCycle,
    IFeedbackIterator,
    IIterationStopPolicy,
    IPipeline,
    IPoemGenerationPipeline,
    IPromptBuilder,
    IRegenerationMerger,
    IRegenerationPromptBuilder,
    IStageFactory,
    IStageSkipPolicy,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.composition.generation_data_plane import (
    GenerationDataPlaneSubContainer,
)
from src.infrastructure.composition.generation_llm_stack import LLMStackSubContainer
from src.infrastructure.pipeline import (
    DefaultPoemGenerationPipeline,
    DefaultStageFactory,
    DefaultStageSkipPolicy,
    SequentialPipeline,
    StageRegistration,
)
from src.infrastructure.prompts import (
    NumberedLinesRegenerationPromptBuilder,
    RagPromptBuilder,
)
from src.infrastructure.regeneration import (
    LineIndexMerger,
    MaxIterationsOrValidStopPolicy,
    ValidatingFeedbackIterator,
)
from src.infrastructure.regeneration.feedback_cycle import ValidationFeedbackCycle
from src.infrastructure.stages import (
    FeedbackLoopStage,
    GenerationStage,
    MetricExamplesStage,
    PromptStage,
    RetrievalStage,
    ValidationStage,
)

if TYPE_CHECKING:
    from src.composition_root import Container


class PipelineStagesSubContainer:
    """Prompt builders, feedback loop, stage registrations, pipeline factories."""

    def __init__(
        self,
        parent: Container,
        data_plane: GenerationDataPlaneSubContainer,
        llm_stack: LLMStackSubContainer,
    ) -> None:
        self._parent = parent
        self._data_plane = data_plane
        self._llm_stack = llm_stack

    # ------------------------------------------------------------------
    # Prompts + regeneration merger
    # ------------------------------------------------------------------

    def regeneration_prompt_builder(self) -> IRegenerationPromptBuilder:
        return self._parent._get(
            CacheKey.REGENERATION_PROMPT_BUILDER,
            NumberedLinesRegenerationPromptBuilder,
        )

    def prompt_builder(self) -> IPromptBuilder:
        return self._parent._get(CacheKey.PROMPT_BUILDER, RagPromptBuilder)

    def regeneration_merger(self) -> IRegenerationMerger:
        return self._parent._get(CacheKey.REGENERATION_MERGER, LineIndexMerger)

    def iteration_stop_policy(self) -> IIterationStopPolicy:
        return self._parent._get(
            CacheKey.ITERATION_STOP_POLICY, MaxIterationsOrValidStopPolicy,
        )

    # ------------------------------------------------------------------
    # Feedback loop
    # ------------------------------------------------------------------

    def feedback_cycle(self) -> IFeedbackCycle:
        return self._parent._get(
            CacheKey.FEEDBACK_CYCLE,
            lambda: ValidationFeedbackCycle(
                meter_validator=self._parent.validation.meter_validator(),
                rhyme_validator=self._parent.validation.rhyme_validator(),
                feedback_formatter=self._parent.validation.feedback_formatter(),
            ),
        )

    def feedback_iterator(self) -> IFeedbackIterator:
        return self._parent._get(
            CacheKey.FEEDBACK_ITERATOR,
            lambda: ValidatingFeedbackIterator(
                llm=self._llm_stack.llm(),
                feedback_cycle=self.feedback_cycle(),
                regeneration_merger=self.regeneration_merger(),
                stop_policy=self.iteration_stop_policy(),
                logger=self._parent.logger,
                llm_call_recorder=self._llm_stack.llm_call_recorder(),
            ),
        )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def skip_policy(self) -> IStageSkipPolicy:
        return self._parent._get(CacheKey.SKIP_POLICY, DefaultStageSkipPolicy)

    def stage_registrations(self) -> list[StageRegistration]:
        def factory() -> list[StageRegistration]:
            skip = self.skip_policy()
            val = self._parent.validation
            return [
                StageRegistration(
                    name=STAGE_RETRIEVAL,
                    stage=RetrievalStage(
                        theme_repo=self._data_plane.theme_repo(),
                        retriever=self._data_plane.retriever(),
                        skip_policy=skip,
                        logger=self._parent.logger,
                    ),
                    togglable=True,
                ),
                StageRegistration(
                    name=STAGE_METRIC_EXAMPLES,
                    stage=MetricExamplesStage(
                        metric_repo=self._data_plane.metric_repo(),
                        skip_policy=skip,
                        logger=self._parent.logger,
                    ),
                    togglable=True,
                ),
                StageRegistration(
                    name=STAGE_PROMPT_CONSTRUCTION,
                    stage=PromptStage(prompt_builder=self.prompt_builder()),
                    togglable=False,
                ),
                StageRegistration(
                    name=STAGE_INITIAL_GENERATION,
                    stage=GenerationStage(
                        llm=self._llm_stack.llm(),
                        logger=self._parent.logger,
                    ),
                    togglable=False,
                ),
                StageRegistration(
                    name=STAGE_VALIDATION,
                    stage=ValidationStage(
                        meter_validator=val.meter_validator(),
                        rhyme_validator=val.rhyme_validator(),
                        feedback_formatter=val.feedback_formatter(),
                        skip_policy=skip,
                        logger=self._parent.logger,
                        record_builder=self._parent.metrics.stage_record_builder(),
                        llm_call_recorder=self._llm_stack.llm_call_recorder(),
                    ),
                    togglable=True,
                ),
                StageRegistration(
                    name=STAGE_FEEDBACK_LOOP,
                    stage=FeedbackLoopStage(
                        iterator=self.feedback_iterator(),
                        skip_policy=skip,
                    ),
                    togglable=True,
                ),
            ]

        return self._parent._get(CacheKey.STAGE_REGISTRATIONS, factory)

    def stage_factory(self) -> IStageFactory:
        return self._parent._get(
            CacheKey.STAGE_FACTORY,
            lambda: DefaultStageFactory(registrations=self.stage_registrations()),
        )

    def generation_pipeline_inner(self) -> IPipeline:
        """IPipeline without final-metrics — used by `PoetryService.generate`."""
        return self._parent._get(
            CacheKey.GENERATION_PIPELINE_INNER,
            lambda: SequentialPipeline(
                stages=self.stage_factory().build_for(frozenset()),
                final_metrics_stage=None,
            ),
        )

    def poem_generation_pipeline(self) -> IPoemGenerationPipeline:
        return self._parent._get(
            CacheKey.POEM_GENERATION_PIPELINE,
            lambda: DefaultPoemGenerationPipeline(
                pipeline=self.generation_pipeline_inner(),
                logger=self._parent.logger,
            ),
        )
