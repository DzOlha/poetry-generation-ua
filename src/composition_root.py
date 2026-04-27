"""Composition root — the single place where concrete classes are wired up.

`Container` is a thin façade that owns five focused sub-containers:

  - `primitives`  : text / stress / phonetics / meter templates / prosody
  - `validation`  : meter validators, rhyme validator, composite poem validator
  - `generation`  : LLM stack, retrieval, prompts, feedback loop, pipeline
  - `metrics`     : metric registry, reporter, tracer factory, error mapper
  - `evaluation`  : scenario registry, evaluation pipeline

Every sub-container shares the same `_cache` so memoisation stays uniform
across the whole graph. The façade exposes the same public accessors the
rest of the project already calls, so tests and services do not care that
the wiring is now split across multiple files.

Handlers, runners and CLI verbs should call only the public `build_*`
factory functions defined here. Concrete classes are NEVER imported by the
application or service layers.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from src.services.detection_service import DetectionService

from src.config import AppConfig
from src.domain.ports import (
    IBatchResultsWriter,
    IClock,
    IDelayer,
    IEmbedder,
    IEvaluationAggregator,
    IFeedbackCycle,
    IFeedbackFormatter,
    IFeedbackIterator,
    IHttpErrorMapper,
    IIterationStopPolicy,
    ILineFeedbackBuilder,
    ILLMProvider,
    ILLMProviderFactory,
    ILogger,
    IMeterCanonicalizer,
    IMeterDetector,
    IMeterValidator,
    IMetricCalculatorRegistry,
    IMetricRepository,
    IPhoneticTranscriber,
    IPipeline,
    IPipelineStage,
    IPoemGenerationPipeline,
    IPoemValidator,
    IPromptBuilder,
    IProviderInfo,
    IRegenerationMerger,
    IRegenerationPromptBuilder,
    IReporter,
    IResultsWriter,
    IRetriever,
    IRhymeDetector,
    IRhymePairAnalyzer,
    IRhymeSchemeExtractor,
    IRhymeValidator,
    IScenarioRegistry,
    IStageFactory,
    IStageRecordBuilder,
    IStageSkipPolicy,
    IStanzaSampler,
    IStressDictionary,
    IStressResolver,
    ISyllableCounter,
    ISyllableFlagStrategy,
    ITextProcessor,
    IThemeRepository,
    ITracerFactory,
    IWeakStressLexicon,
)
from src.domain.ports.prosody import IMeterTemplateProvider, IProsodyAnalyzer
from src.infrastructure.composition import (
    DetectionSubContainer,
    EvaluationSubContainer,
    GenerationSubContainer,
    MetricsSubContainer,
    PrimitivesSubContainer,
    ValidationSubContainer,
)
from src.infrastructure.logging import StdOutLogger
from src.services.batch_evaluation_service import BatchEvaluationService
from src.services.evaluation_service import EvaluationService
from src.services.poetry_service import PoetryService

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Container — thin façade composing five sub-containers over a shared cache
# ---------------------------------------------------------------------------

@dataclass
class Container:
    """Lazy, single-instance cache for shared adapters within one composition.

    All adapter construction goes through one of the five sub-containers
    (primitives, validation, generation, metrics, evaluation). Every
    sub-container dispatches memoisation through the same `_get(key, factory)`
    call on the parent, so there is a single cache for the whole graph.

    Public convenience methods (`meter_validator`, `rhyme_validator`, etc.)
    delegate to the matching sub-container — this keeps existing call sites
    ergonomic while the per-topic wiring lives in focused files.
    """

    config: AppConfig
    logger: ILogger
    injected_llm: ILLMProvider | None = None
    _cache: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.primitives: PrimitivesSubContainer = PrimitivesSubContainer(self)
        self.validation: ValidationSubContainer = ValidationSubContainer(self)
        self.generation: GenerationSubContainer = GenerationSubContainer(self)
        self.metrics: MetricsSubContainer = MetricsSubContainer(self)
        self.evaluation: EvaluationSubContainer = EvaluationSubContainer(self)
        self.detection_sub: DetectionSubContainer = DetectionSubContainer(self)

    def _get(self, key: str, factory: Callable[[], T]) -> T:
        """Return a cached adapter instance, creating it lazily on first access.

        Every sub-container calls this method so the entire object graph shares
        a single cache and each adapter is instantiated at most once.
        """
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    # ------------------------------------------------------------------
    # Primitives delegation
    # ------------------------------------------------------------------

    def clock(self) -> IClock:
        return self.primitives.clock()

    def delayer(self) -> IDelayer:
        return self.primitives.delayer()

    def text_processor(self) -> ITextProcessor:
        return self.primitives.text_processor()

    def stress_dict(self) -> IStressDictionary:
        return self.primitives.stress_dict()

    def syllable_counter(self) -> ISyllableCounter:
        return self.primitives.syllable_counter()

    def stress_resolver(self) -> IStressResolver:
        return self.primitives.stress_resolver()

    def phonetic_transcriber(self) -> IPhoneticTranscriber:
        return self.primitives.phonetic_transcriber()

    def meter_canonicalizer(self) -> IMeterCanonicalizer:
        return self.primitives.meter_canonicalizer()

    def meter_template_provider(self) -> IMeterTemplateProvider:
        return self.primitives.meter_template_provider()

    def weak_stress_lexicon(self) -> IWeakStressLexicon:
        return self.primitives.weak_stress_lexicon()

    def syllable_flag_strategy(self) -> ISyllableFlagStrategy:
        return self.primitives.syllable_flag_strategy()

    def prosody(self) -> IProsodyAnalyzer:
        return self.primitives.prosody()

    def line_feedback_builder(self) -> ILineFeedbackBuilder:
        return self.primitives.line_feedback_builder()

    # ------------------------------------------------------------------
    # Validation delegation
    # ------------------------------------------------------------------

    def bsp_meter_validator(self) -> IMeterValidator:
        """Return the binary-stress-pattern meter validator (alternative strategy)."""
        return self.validation.bsp_meter_validator()

    def meter_validator(self) -> IMeterValidator:
        return self.validation.meter_validator()

    def rhyme_scheme_extractor(self) -> IRhymeSchemeExtractor:
        return self.validation.rhyme_scheme_extractor()

    def rhyme_pair_analyzer(self) -> IRhymePairAnalyzer:
        return self.validation.rhyme_pair_analyzer()

    def rhyme_validator(self) -> IRhymeValidator:
        return self.validation.rhyme_validator()

    def poem_validator(self) -> IPoemValidator:
        return self.validation.poem_validator()

    def feedback_formatter(self) -> IFeedbackFormatter:
        return self.validation.feedback_formatter()

    # ------------------------------------------------------------------
    # Generation delegation
    # ------------------------------------------------------------------

    def theme_repo(self) -> IThemeRepository:
        return self.generation.theme_repo()

    def metric_repo(self) -> IMetricRepository:
        return self.generation.metric_repo()

    def embedder(self) -> IEmbedder:
        return self.generation.embedder()

    def retriever(self) -> IRetriever:
        return self.generation.retriever()

    def regeneration_prompt_builder(self) -> IRegenerationPromptBuilder:
        return self.generation.regeneration_prompt_builder()

    def prompt_builder(self) -> IPromptBuilder:
        return self.generation.prompt_builder()

    def regeneration_merger(self) -> IRegenerationMerger:
        return self.generation.regeneration_merger()

    def iteration_stop_policy(self) -> IIterationStopPolicy:
        return self.generation.iteration_stop_policy()

    def llm_factory(self) -> ILLMProviderFactory:
        return self.generation.llm_factory()

    def llm(self) -> ILLMProvider:
        """Return the fully decorated LLM provider (logging -> retry -> timeout)."""
        return self.generation.llm()

    def provider_info(self) -> IProviderInfo:
        return self.generation.provider_info()

    def feedback_cycle(self) -> IFeedbackCycle:
        return self.generation.feedback_cycle()

    def feedback_iterator(self) -> IFeedbackIterator:
        return self.generation.feedback_iterator()

    def skip_policy(self) -> IStageSkipPolicy:
        return self.generation.skip_policy()

    def stage_factory(self) -> IStageFactory:
        return self.generation.stage_factory()

    def generation_pipeline_inner(self) -> IPipeline:
        """Return the raw sequential pipeline without tracing or default config."""
        return self.generation.generation_pipeline_inner()

    def poem_generation_pipeline(self) -> IPoemGenerationPipeline:
        """Return the top-level pipeline wrapping generation, validation, and feedback."""
        return self.generation.poem_generation_pipeline()

    # ------------------------------------------------------------------
    # Metrics delegation
    # ------------------------------------------------------------------

    def metric_registry(self) -> IMetricCalculatorRegistry:
        return self.metrics.metric_registry()

    def final_metrics_stage(self) -> IPipelineStage:
        """Return the optional terminal stage that computes evaluation metrics."""
        return self.metrics.final_metrics_stage()

    def reporter(self) -> IReporter:
        return self.metrics.reporter()

    def results_writer(self) -> IResultsWriter:
        return self.metrics.results_writer()

    def batch_results_writer(self) -> IBatchResultsWriter:
        return self.metrics.batch_results_writer()

    def tracer_factory(self) -> ITracerFactory:
        return self.metrics.tracer_factory()

    def http_error_mapper(self) -> IHttpErrorMapper:
        """Return the mapper that translates DomainError subtypes to HTTP status codes."""
        return self.metrics.http_error_mapper()

    def stage_record_builder(self) -> IStageRecordBuilder:
        return self.metrics.stage_record_builder()

    def evaluation_aggregator(self) -> IEvaluationAggregator:
        return self.metrics.evaluation_aggregator()

    # ------------------------------------------------------------------
    # Evaluation delegation
    # ------------------------------------------------------------------

    def scenario_registry(self) -> IScenarioRegistry:
        return self.evaluation.scenario_registry()

    def evaluation_pipeline(self) -> IPipeline:
        """Return the evaluation-specific pipeline that includes the final metrics stage."""
        return self.evaluation.evaluation_pipeline()

    # ------------------------------------------------------------------
    # Detection delegation
    # ------------------------------------------------------------------

    def stanza_sampler(self) -> IStanzaSampler:
        return self.detection_sub.stanza_sampler()

    def meter_detector(self) -> IMeterDetector:
        return self.detection_sub.meter_detector()

    def rhyme_detector(self) -> IRhymeDetector:
        return self.detection_sub.rhyme_detector()


# ---------------------------------------------------------------------------
# Public top-level factories
# ---------------------------------------------------------------------------

def build_logger(config: AppConfig | None = None) -> ILogger:
    """Return a process-wide logger. `config` is accepted for symmetry but unused today."""
    del config
    return StdOutLogger()


def build_container(
    config: AppConfig,
    logger: ILogger | None = None,
    *,
    llm: ILLMProvider | None = None,
) -> Container:
    """Return a fresh composition container.

    Handlers that need both `PoetryService` and `EvaluationService` should
    build a single container and pull both services from it so every
    adapter is shared (same embedder, same validators, same LLM instance).
    """
    return Container(
        config=config,
        logger=logger or build_logger(config),
        injected_llm=llm,
    )


def build_poetry_service(
    config: AppConfig,
    logger: ILogger | None = None,
    *,
    container: Container | None = None,
) -> PoetryService:
    """Wire and return a fully configured PoetryService."""
    c = container or build_container(config=config, logger=logger)
    return PoetryService(
        generation_pipeline=c.poem_generation_pipeline(),
        poem_validator=c.poem_validator(),
        provider_info=c.provider_info(),
        logger=c.logger,
    )


def build_evaluation_service(
    config: AppConfig,
    logger: ILogger | None = None,
    *,
    llm: ILLMProvider | None = None,
    container: Container | None = None,
) -> EvaluationService:
    """Wire and return a fully configured EvaluationService."""
    from src.domain.evaluation import ABLATION_CONFIGS

    c = container or build_container(config=config, logger=logger, llm=llm)
    return EvaluationService(
        pipeline=c.evaluation_pipeline(),
        tracer_factory=c.tracer_factory(),
        logger=c.logger,
        scenario_registry=c.scenario_registry(),
        ablation_configs=ABLATION_CONFIGS,
        clock=c.clock(),
    )


def build_batch_evaluation_service(
    config: AppConfig,
    logger: ILogger | None = None,
    *,
    llm: ILLMProvider | None = None,
    container: Container | None = None,
) -> BatchEvaluationService:
    """Wire and return a fully configured BatchEvaluationService."""
    c = container or build_container(config=config, logger=logger, llm=llm)
    return BatchEvaluationService(
        evaluation_service=build_evaluation_service(config, logger=logger, llm=llm, container=c),
        writer=c.batch_results_writer(),
        logger=c.logger,
        delayer=c.delayer(),
    )


def build_detection_service(
    config: AppConfig,
    logger: ILogger | None = None,
    *,
    container: Container | None = None,
) -> DetectionService:
    """Wire and return a fully configured DetectionService."""
    from src.services.detection_service import DetectionService

    c = container or build_container(config=config, logger=logger)
    return DetectionService(
        sampler=c.stanza_sampler(),
        meter_detector=c.meter_detector(),
        rhyme_detector=c.rhyme_detector(),
        config=c.config.detection,
        logger=c.logger,
    )


# ---------------------------------------------------------------------------
# Convenience factories — delegate to a temporary container for consistency.
# Prefer `build_container(config).reporter()` over these when you already
# have a config and want memoised adapters.
# ---------------------------------------------------------------------------

def build_reporter(config: AppConfig | None = None) -> IReporter:
    """Return a reporter.  Uses a container so the adapter is consistent."""
    c = build_container(config or AppConfig.from_env())
    return c.reporter()


def build_feedback_formatter(config: AppConfig | None = None) -> IFeedbackFormatter:
    """Return a feedback formatter via the container."""
    c = build_container(config or AppConfig.from_env())
    return c.feedback_formatter()


def build_regeneration_prompt_builder(config: AppConfig | None = None) -> IRegenerationPromptBuilder:
    """Return a regeneration prompt builder via the container."""
    c = build_container(config or AppConfig.from_env())
    return c.regeneration_prompt_builder()


def build_results_writer(reporter: IReporter | None = None, config: AppConfig | None = None) -> IResultsWriter:  # noqa: ARG001
    """Return a results writer via the container."""
    c = build_container(config or AppConfig.from_env())
    return c.results_writer()
