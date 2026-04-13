"""Core infrastructure fixtures — low-level adapters built explicitly."""
from __future__ import annotations

from typing import Any

import pytest

from src.domain.models import ThemeExcerpt
from src.domain.ports import (
    IFeedbackFormatter,
    ILogger,
    IStressDictionary,
    IStressResolver,
)
from src.infrastructure.embeddings.labse import OfflineDeterministicEmbedder
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.logging import NullLogger
from src.infrastructure.meter import (
    DefaultSyllableFlagStrategy,
    UkrainianMeterCanonicalizer,
    UkrainianMeterTemplateProvider,
    UkrainianWeakStressLexicon,
)
from src.infrastructure.phonetics import UkrainianIpaTranscriber
from src.infrastructure.repositories.theme_repository import DemoThemeRepository
from src.infrastructure.retrieval.semantic_retriever import SemanticRetriever
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianStressDict,
    UkrainianSyllableCounter,
)
from src.infrastructure.text import UkrainianTextProcessor


class RecordingLogger(ILogger):
    """Test double that records all log calls for assertion."""

    def __init__(self) -> None:
        self.infos: list[tuple[str, dict[str, Any]]] = []
        self.warnings: list[tuple[str, dict[str, Any]]] = []
        self.errors: list[tuple[str, dict[str, Any]]] = []

    def info(self, message: str, **fields: Any) -> None:
        self.infos.append((message, fields))

    def warning(self, message: str, **fields: Any) -> None:
        self.warnings.append((message, fields))

    def error(self, message: str, **fields: Any) -> None:
        self.errors.append((message, fields))


@pytest.fixture
def null_logger() -> ILogger:
    return NullLogger()


@pytest.fixture
def stress_dict(null_logger) -> IStressDictionary:
    return UkrainianStressDict(logger=null_logger, on_ambiguity="first")


@pytest.fixture
def syllable_counter() -> UkrainianSyllableCounter:
    return UkrainianSyllableCounter()


@pytest.fixture
def stress_resolver(
    stress_dict: IStressDictionary,
    syllable_counter: UkrainianSyllableCounter,
) -> IStressResolver:
    return PenultimateFallbackStressResolver(
        stress_dictionary=stress_dict,
        syllable_counter=syllable_counter,
    )


@pytest.fixture
def text_processor() -> UkrainianTextProcessor:
    return UkrainianTextProcessor()


@pytest.fixture
def meter_template_provider() -> UkrainianMeterTemplateProvider:
    return UkrainianMeterTemplateProvider()


@pytest.fixture
def weak_stress_lexicon() -> UkrainianWeakStressLexicon:
    return UkrainianWeakStressLexicon()


@pytest.fixture
def syllable_flag_strategy(weak_stress_lexicon) -> DefaultSyllableFlagStrategy:
    return DefaultSyllableFlagStrategy(weak_stress_lexicon=weak_stress_lexicon)


@pytest.fixture
def meter_canonicalizer() -> UkrainianMeterCanonicalizer:
    return UkrainianMeterCanonicalizer()


@pytest.fixture
def phonetic_transcriber() -> UkrainianIpaTranscriber:
    return UkrainianIpaTranscriber()


@pytest.fixture
def offline_embedder(null_logger) -> OfflineDeterministicEmbedder:
    return OfflineDeterministicEmbedder(logger=null_logger)


@pytest.fixture
def regeneration_prompt_builder():
    from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder

    return NumberedLinesRegenerationPromptBuilder()


@pytest.fixture
def mock_llm(regeneration_prompt_builder) -> MockLLMProvider:
    return MockLLMProvider(regeneration_prompt_builder=regeneration_prompt_builder)


@pytest.fixture
def demo_corpus() -> list[ThemeExcerpt]:
    return DemoThemeRepository().load()


@pytest.fixture
def retriever(offline_embedder) -> SemanticRetriever:
    return SemanticRetriever(offline_embedder)


@pytest.fixture
def feedback_formatter() -> IFeedbackFormatter:
    from src.infrastructure.feedback import UkrainianFeedbackFormatter

    return UkrainianFeedbackFormatter()
