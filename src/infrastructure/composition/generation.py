"""Generation sub-container.

Owns the data plane (LLM, theme/metric repositories, embedder, retriever),
prompt builders, the feedback loop stack, the pipeline stage
registrations, and the concrete `IPipeline` / `IPoemGenerationPipeline`.

LLM construction goes through a reliability stack (timeout → retry →
logging) so every production caller inherits the same reliability
behaviour without each one re-implementing retry/timeout by hand.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.config import LLMReliabilityConfig
from src.domain.evaluation import (
    STAGE_FEEDBACK_LOOP,
    STAGE_INITIAL_GENERATION,
    STAGE_METRIC_EXAMPLES,
    STAGE_PROMPT_CONSTRUCTION,
    STAGE_RETRIEVAL,
    STAGE_VALIDATION,
)
from src.domain.ports import (
    IEmbedder,
    IFeedbackCycle,
    IFeedbackIterator,
    IIterationStopPolicy,
    ILLMProvider,
    ILLMProviderFactory,
    IMetricRepository,
    IPipeline,
    IPoemGenerationPipeline,
    IPromptBuilder,
    IProviderInfo,
    IRegenerationMerger,
    IRegenerationPromptBuilder,
    IRetriever,
    IStageFactory,
    IStageSkipPolicy,
    IThemeRepository,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.embeddings import (
    CompositeEmbedder,
    LaBSEEmbedder,
    OfflineDeterministicEmbedder,
)
from src.infrastructure.llm import DefaultLLMProviderFactory
from src.infrastructure.llm.decorators import (
    ExponentialBackoffRetry,
    LoggingLLMProvider,
    RetryingLLMProvider,
    TimeoutLLMProvider,
)
from src.infrastructure.llm.provider_info import LLMProviderInfo
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
from src.infrastructure.repositories.metric_repository import JsonMetricRepository
from src.infrastructure.repositories.theme_repository import (
    DemoThemeRepository,
    JsonThemeRepository,
)
from src.infrastructure.retrieval import SemanticRetriever
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


class GenerationSubContainer:
    """LLM, retrieval, prompts, feedback loop, and pipeline wiring."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    # ------------------------------------------------------------------
    # Data plane (repos, embedder, retriever)
    # ------------------------------------------------------------------

    def theme_repo(self) -> IThemeRepository:
        def factory() -> IThemeRepository:
            cfg = self._parent.config
            if Path(cfg.corpus_path).exists():
                return JsonThemeRepository(path=cfg.corpus_path)
            return DemoThemeRepository()

        return self._parent._get(CacheKey.THEME_REPO, factory)

    def metric_repo(self) -> IMetricRepository:
        return self._parent._get(
            CacheKey.METRIC_REPO,
            lambda: JsonMetricRepository(
                path=self._parent.config.metric_examples_path,
                meter_canonicalizer=self._parent.primitives.meter_canonicalizer(),
            ),
        )

    def embedder(self) -> IEmbedder:
        def factory() -> IEmbedder:
            cfg = self._parent.config
            offline = OfflineDeterministicEmbedder(logger=self._parent.logger)
            if cfg.offline_embedder:
                return offline
            primary = LaBSEEmbedder(
                logger=self._parent.logger, model_name=cfg.labse_model_name,
            )
            # CompositeEmbedder falls back to the offline embedder on
            # runtime LaBSE failures (model missing, network down, OOM).
            return CompositeEmbedder(
                primary=primary,
                fallback=offline,
                logger=self._parent.logger,
            )

        return self._parent._get(CacheKey.EMBEDDER, factory)

    def retriever(self) -> IRetriever:
        return self._parent._get(
            CacheKey.RETRIEVER,
            lambda: SemanticRetriever(embedder=self.embedder()),
        )

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
    # LLM provider stack (raw → timeout → retry → logging)
    # ------------------------------------------------------------------

    def llm_factory(self) -> ILLMProviderFactory:
        return self._parent._get(
            CacheKey.LLM_FACTORY,
            lambda: DefaultLLMProviderFactory(config=self._parent.config),
        )

    def llm(self) -> ILLMProvider:
        def factory() -> ILLMProvider:
            if self._parent.injected_llm is not None:
                # Test/CI mocks do not get wrapped; they never fail or hang.
                return self._parent.injected_llm
            raw = self.llm_factory().create(self.regeneration_prompt_builder())
            return self._wrap_with_reliability(raw)

        return self._parent._get(CacheKey.LLM, factory)

    def _wrap_with_reliability(self, provider: ILLMProvider) -> ILLMProvider:
        rel: LLMReliabilityConfig = self._parent.config.llm_reliability
        timed = TimeoutLLMProvider(
            inner=provider,
            timeout_sec=rel.timeout_sec,
        )
        retrying = RetryingLLMProvider(
            inner=timed,
            policy=ExponentialBackoffRetry(
                max_attempts=rel.retry_max_attempts,
                base_delay_sec=rel.retry_base_delay_sec,
                max_delay_sec=rel.retry_max_delay_sec,
                multiplier=rel.retry_multiplier,
            ),
            logger=self._parent.logger,
        )
        return LoggingLLMProvider(inner=retrying, logger=self._parent.logger)

    def provider_info(self) -> IProviderInfo:
        return self._parent._get(
            CacheKey.PROVIDER_INFO,
            lambda: LLMProviderInfo(self.llm()),
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
                llm=self.llm(),
                feedback_cycle=self.feedback_cycle(),
                regeneration_merger=self.regeneration_merger(),
                stop_policy=self.iteration_stop_policy(),
                logger=self._parent.logger,
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
                        theme_repo=self.theme_repo(),
                        retriever=self.retriever(),
                        skip_policy=skip,
                        logger=self._parent.logger,
                    ),
                    togglable=True,
                ),
                StageRegistration(
                    name=STAGE_METRIC_EXAMPLES,
                    stage=MetricExamplesStage(
                        metric_repo=self.metric_repo(),
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
                        llm=self.llm(),
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
