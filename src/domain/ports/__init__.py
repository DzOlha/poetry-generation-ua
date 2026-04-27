"""Abstract interfaces (ports) that define the system's extension points.

All infrastructure adapters implement these interfaces. Services depend
only on these abstractions — never on concrete classes. Every interface
follows ISP: small, focused, easy to implement and mock.

Organised into focused modules:

  ports.corpus      — ParsedPoem, ICorpusParser
  ports.detection   — IStanzaSampler, IMeterDetector, IRhymeDetector, IDetectionService
  ports.logging     — ILogger
  ports.text        — ILineSplitter, ITokenizer, IStringSimilarity, ITextProcessor
  ports.stress      — IStressDictionary, ISyllableCounter, IStressResolver,
                      IPhoneticTranscriber, IMeterCanonicalizer
  ports.prosody     — IMeterTemplateProvider, IWeakStressLexicon,
                      ISyllableFlagStrategy, IProsodyAnalyzer, ILineFeedbackBuilder, ...
  ports.data        — ILLMProvider, ILLMProviderFactory, IThemeRepository,
                      IMetricRepository, IEmbedder
  ports.retrieval   — IRetriever
  ports.validation  — IMeterValidator, IRhymeValidator, IPoemValidator
  ports.prompts     — IPromptBuilder, IRegenerationPromptBuilder,
                      IRegenerationMerger, IFeedbackFormatter
  ports.rhyme       — IRhymeSchemeExtractor, RhymePairAnalysis, IRhymePairAnalyzer
  ports.metrics     — EvaluationContext, IMetricCalculator, IMetricCalculatorRegistry
  ports.pipeline    — IPipelineStage, IStageSkipPolicy, IStageFactory, IPipeline,
                      IFeedbackCycle, IFeedbackIterator, IPoemGenerationPipeline, ...
  ports.tracing     — ITraceRecorder, ITraceReader, ITracer, ITracerFactory
  ports.reporting   — IReporter, IResultsWriter
  ports.runner      — IRunner
  ports.http        — HttpErrorResponse, IHttpErrorMapper
  ports.evaluation  — IScenarioRegistry, IEvaluationAggregator,
                      IStageRecordBuilder, aggregation dataclasses

All names are re-exported here so ``from src.domain.ports import X``
continues to work unchanged.
"""

# -- Corpus --
# -- Feedback utility (lives in domain.models.feedback, re-exported for convenience) --
from src.domain.models.feedback import format_all_feedback  # noqa: E402
from src.domain.ports.corpus import ICorpusParser, ParsedPoem

# -- Data plane --
from src.domain.ports.data import (
    IEmbedder,
    ILLMProvider,
    ILLMProviderFactory,
    IMetricRepository,
    IProviderInfo,
    IRetryPolicy,
    IThemeRepository,
)

# -- Detection --
from src.domain.ports.detection import (
    IDetectionService,
    IMeterDetector,
    IRhymeDetector,
    IStanzaSampler,
)

# -- Evaluation --
from src.domain.ports.evaluation import (
    CategoryAggregate,
    ConfigAggregate,
    EvaluationAggregates,
    IEvaluationAggregator,
    IScenarioRegistry,
    IStageRecordBuilder,
)

# -- HTTP --
from src.domain.ports.http import HttpErrorResponse, IHttpErrorMapper
from src.domain.ports.llm_trace import ILLMCallRecorder, LLMCallSnapshot
from src.domain.ports.logging import ILogger

# -- Metrics --
from src.domain.ports.metrics import (
    EvaluationContext,
    IMetricCalculator,
    IMetricCalculatorRegistry,
)

# -- Pipeline --
from src.domain.ports.pipeline import (
    FeedbackCycleOutcome,
    IFeedbackCycle,
    IFeedbackIterator,
    IIterationStopPolicy,
    IPipeline,
    IPipelineStage,
    IPoemGenerationPipeline,
    IStageFactory,
    IStageSkipPolicy,
)

# -- Prompts & regeneration --
from src.domain.ports.prompts import (
    IFeedbackFormatter,
    IPromptBuilder,
    IRegenerationMerger,
    IRegenerationPromptBuilder,
)

# -- Prosody --
from src.domain.ports.prosody import (
    IExpectedMeterBuilder,
    ILineFeedbackBuilder,
    IMeterTemplateProvider,
    IMismatchTolerance,
    IProsodyAnalyzer,
    IStressPatternAnalyzer,
    ISyllableFlagStrategy,
    IWeakStressLexicon,
)

# -- Reporting --
from src.domain.ports.reporting import IReporter, IResultsWriter

# -- Retrieval --
from src.domain.ports.retrieval import IRetriever

# -- Rhyme analysis --
from src.domain.ports.rhyme import (
    IRhymePairAnalyzer,
    IRhymeSchemeExtractor,
    RhymePairAnalysis,
)

# -- Runner --
from src.domain.ports.runner import IRunner

# -- Sanitization --
from src.domain.ports.sanitization import IPoemExtractor, IPoemOutputSanitizer

# -- Stress & phonetics --
from src.domain.ports.stress import (
    IMeterCanonicalizer,
    IPhoneticTranscriber,
    IStressDictionary,
    IStressResolver,
    ISyllableCounter,
)

# -- Text --
from src.domain.ports.text import (
    ILineSplitter,
    IStringSimilarity,
    ITextProcessor,
    ITokenizer,
)

# -- Tracing --
from src.domain.ports.tracing import (
    ITracer,
    ITraceReader,
    ITraceRecorder,
    ITracerFactory,
)

# -- Validation --
from src.domain.ports.validation import (
    IMeterValidator,
    IPoemValidator,
    IRhymeValidator,
)

# -- Value objects --
from src.domain.value_objects import ClausulaType, RhymePrecision

__all__ = [
    # Corpus
    "ParsedPoem",
    "ICorpusParser",
    # Detection
    "IStanzaSampler",
    "IMeterDetector",
    "IRhymeDetector",
    "IDetectionService",
    # Logging
    "ILogger",
    # LLM call tracing
    "ILLMCallRecorder",
    "LLMCallSnapshot",
    # Text
    "ILineSplitter",
    "ITokenizer",
    "IStringSimilarity",
    "ITextProcessor",
    # Stress & phonetics
    "IStressDictionary",
    "ISyllableCounter",
    "IStressResolver",
    "IPhoneticTranscriber",
    "IMeterCanonicalizer",
    # Prosody
    "IMeterTemplateProvider",
    "IWeakStressLexicon",
    "ISyllableFlagStrategy",
    "IStressPatternAnalyzer",
    "IExpectedMeterBuilder",
    "IMismatchTolerance",
    "IProsodyAnalyzer",
    "ILineFeedbackBuilder",
    # Data plane
    "ILLMProvider",
    "IProviderInfo",
    "IRetryPolicy",
    "ILLMProviderFactory",
    "IThemeRepository",
    "IMetricRepository",
    "IEmbedder",
    # Retrieval
    "IRetriever",
    # Validation
    "IMeterValidator",
    "IRhymeValidator",
    "IPoemValidator",
    # Prompts & regeneration
    "IPromptBuilder",
    "IRegenerationPromptBuilder",
    "IRegenerationMerger",
    "IFeedbackFormatter",
    "format_all_feedback",
    # Rhyme analysis
    "IRhymeSchemeExtractor",
    "RhymePairAnalysis",
    "IRhymePairAnalyzer",
    # Sanitization
    "IPoemExtractor",
    "IPoemOutputSanitizer",
    # Value objects (re-exported from models for convenience)
    "ClausulaType",
    "RhymePrecision",
    # Metrics
    "EvaluationContext",
    "IMetricCalculator",
    "IMetricCalculatorRegistry",
    # Tracing
    "ITraceRecorder",
    "ITraceReader",
    "ITracer",
    "ITracerFactory",
    # Reporting
    "IReporter",
    "IResultsWriter",
    # Pipeline
    "IPipelineStage",
    "IStageSkipPolicy",
    "IStageFactory",
    "IPipeline",
    "IIterationStopPolicy",
    "FeedbackCycleOutcome",
    "IFeedbackCycle",
    "IFeedbackIterator",
    "IPoemGenerationPipeline",
    # Runner
    "IRunner",
    # HTTP
    "HttpErrorResponse",
    "IHttpErrorMapper",
    # Evaluation
    "IScenarioRegistry",
    "ConfigAggregate",
    "CategoryAggregate",
    "EvaluationAggregates",
    "IEvaluationAggregator",
    "IStageRecordBuilder",
]
