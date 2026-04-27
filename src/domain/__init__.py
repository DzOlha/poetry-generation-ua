"""Domain layer — value objects, entities, DTOs, and abstract ports.

Modules:
  models           — immutable data containers (value objects, command/result objects,
                     LineFeedback/PairFeedback, CorpusEntry/MetricCorpusEntry)
  values           — meter/rhyme/category enums
  errors           — DomainError hierarchy
  evaluation       — AblationConfig, traces, summaries
  scenarios        — EvaluationScenario dataclass + ScenarioRegistry
  ports            — abstract interfaces
  pipeline_context — shared state for pipeline stages
"""
from src.domain.errors import (
    ConfigurationError,
    DomainError,
    EmbedderError,
    LLMError,
    RepositoryError,
    StressDictionaryError,
    UnsupportedConfigError,
    ValidationError,
)
from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    LineMeterResult,
    MeterResult,
    MeterSpec,
    MetricExample,
    MetricQuery,
    PoemStructure,
    RetrievedExcerpt,
    RhymePairResult,
    RhymeResult,
    RhymeScheme,
    ThemeExcerpt,
    ValidationRequest,
    ValidationResult,
)
from src.domain.models.feedback import LineFeedback, PairFeedback
from src.domain.ports import (
    CategoryAggregate,
    ConfigAggregate,
    EvaluationAggregates,
    EvaluationContext,
    HttpErrorResponse,
    IEmbedder,
    IEvaluationAggregator,
    IFeedbackFormatter,
    IHttpErrorMapper,
    ILLMProvider,
    ILogger,
    IMeterValidator,
    IMetricCalculator,
    IMetricRepository,
    IPipelineStage,
    IPromptBuilder,
    IProsodyAnalyzer,
    IRegenerationMerger,
    IRegenerationPromptBuilder,
    IReporter,
    IRhymeSchemeExtractor,
    IRhymeValidator,
    IRunner,
    IScenarioRegistry,
    IStageRecordBuilder,
    IStressDictionary,
    ITextProcessor,
    IThemeRepository,
    ITracer,
    ITraceReader,
    ITraceRecorder,
    ITracerFactory,
)
from src.domain.values import MeterName, RhymePattern, ScenarioCategory

__all__ = [
    # values / enums
    "MeterName", "RhymePattern", "ScenarioCategory",
    # errors
    "DomainError", "ConfigurationError", "UnsupportedConfigError",
    "ValidationError", "RepositoryError", "LLMError",
    "EmbedderError", "StressDictionaryError",
    # feedback
    "LineFeedback", "PairFeedback",
    # models
    "MeterSpec", "RhymeScheme", "PoemStructure",
    "GenerationRequest", "ValidationRequest",
    "LineMeterResult", "RhymePairResult",
    "MeterResult", "RhymeResult", "ValidationResult", "GenerationResult",
    "ThemeExcerpt", "MetricExample", "MetricQuery", "RetrievedExcerpt",
    # ports
    "ILogger", "IStressDictionary", "ILLMProvider",
    "IThemeRepository", "IMetricRepository", "IEmbedder",
    "IMeterValidator", "IRhymeValidator",
    "IPromptBuilder", "IRegenerationPromptBuilder", "IRegenerationMerger",
    "IFeedbackFormatter",
    "ITextProcessor", "IProsodyAnalyzer", "IRhymeSchemeExtractor",
    "IMetricCalculator", "EvaluationContext",
    "ITracer", "ITraceRecorder", "ITraceReader", "ITracerFactory", "IReporter",
    "IPipelineStage", "IRunner",
    "IScenarioRegistry",
    "IHttpErrorMapper", "HttpErrorResponse",
    "IEvaluationAggregator", "ConfigAggregate", "CategoryAggregate", "EvaluationAggregates",
    "IStageRecordBuilder",
]
