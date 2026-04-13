"""Cache key constants for the composition root.

Centralises all string keys used by ``Container._get()`` so that
sub-containers share a single source of truth and key collisions are
caught statically (duplicate enum members raise at import time).
"""
from __future__ import annotations

from enum import Enum, unique


@unique
class CacheKey(str, Enum):
    """Every adapter instance stored in the Container cache."""

    # Primitives
    TEXT_PROCESSOR = "text_processor"
    STRING_SIMILARITY = "string_similarity"
    STRESS_DICT = "stress_dict"
    SYLLABLE_COUNTER = "syllable_counter"
    STRESS_RESOLVER = "stress_resolver"
    PHONETIC_TRANSCRIBER = "phonetic_transcriber"
    METER_CANONICALIZER = "meter_canonicalizer"
    METER_TEMPLATE_PROVIDER = "meter_template_provider"
    WEAK_STRESS_LEXICON = "weak_stress_lexicon"
    SYLLABLE_FLAG_STRATEGY = "syllable_flag_strategy"
    PROSODY = "prosody"
    LINE_FEEDBACK_BUILDER = "line_feedback_builder"

    # Validation
    BSP_ALGORITHM = "bsp_algorithm"
    BSP_METER_VALIDATOR = "bsp_meter_validator"
    METER_VALIDATOR = "meter_validator"
    RHYME_SCHEME_EXTRACTOR = "rhyme_scheme_extractor"
    RHYME_PAIR_ANALYZER = "rhyme_pair_analyzer"
    RHYME_VALIDATOR = "rhyme_validator"
    POEM_VALIDATOR = "poem_validator"
    FEEDBACK_FORMATTER = "feedback_formatter"

    # Generation
    THEME_REPO = "theme_repo"
    METRIC_REPO = "metric_repo"
    EMBEDDER = "embedder"
    RETRIEVER = "retriever"
    REGENERATION_PROMPT_BUILDER = "regeneration_prompt_builder"
    PROMPT_BUILDER = "prompt_builder"
    REGENERATION_MERGER = "regeneration_merger"
    ITERATION_STOP_POLICY = "iteration_stop_policy"
    LLM_FACTORY = "llm_factory"
    LLM = "llm"
    PROVIDER_INFO = "provider_info"
    FEEDBACK_CYCLE = "feedback_cycle"
    FEEDBACK_ITERATOR = "feedback_iterator"
    SKIP_POLICY = "skip_policy"
    STAGE_REGISTRATIONS = "stage_registrations"
    STAGE_FACTORY = "stage_factory"
    GENERATION_PIPELINE_INNER = "generation_pipeline_inner"
    POEM_GENERATION_PIPELINE = "poem_generation_pipeline"

    # Metrics
    METRIC_REGISTRY = "metric_registry"
    FINAL_METRICS_STAGE = "final_metrics_stage"
    REPORTER = "reporter"
    RESULTS_WRITER = "results_writer"
    TRACER_FACTORY = "tracer_factory"
    HTTP_ERROR_MAPPER = "http_error_mapper"
    STAGE_RECORD_BUILDER = "stage_record_builder"
    EVALUATION_AGGREGATOR = "evaluation_aggregator"

    # Evaluation
    SCENARIO_REGISTRY = "scenario_registry"
    EVALUATION_PIPELINE = "evaluation_pipeline"

    # Detection
    STANZA_SAMPLER = "stanza_sampler"
    METER_DETECTOR = "meter_detector"
    RHYME_DETECTOR = "rhyme_detector"
