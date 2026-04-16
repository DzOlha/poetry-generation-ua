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


# --- Session-scoped heavy resources (loaded once per test run) ---

@pytest.fixture(scope="session")
def _session_logger() -> ILogger:
    return NullLogger()


@pytest.fixture(scope="session")
def stress_dict(_session_logger) -> IStressDictionary:
    return UkrainianStressDict(logger=_session_logger, on_ambiguity="first")


@pytest.fixture(scope="session")
def syllable_counter() -> UkrainianSyllableCounter:
    return UkrainianSyllableCounter()


@pytest.fixture(scope="session")
def stress_resolver(
    stress_dict: IStressDictionary,
    syllable_counter: UkrainianSyllableCounter,
) -> IStressResolver:
    return PenultimateFallbackStressResolver(
        stress_dictionary=stress_dict,
        syllable_counter=syllable_counter,
    )


@pytest.fixture(scope="session")
def text_processor() -> UkrainianTextProcessor:
    return UkrainianTextProcessor()


@pytest.fixture(scope="session")
def meter_template_provider() -> UkrainianMeterTemplateProvider:
    return UkrainianMeterTemplateProvider()


@pytest.fixture(scope="session")
def weak_stress_lexicon() -> UkrainianWeakStressLexicon:
    return UkrainianWeakStressLexicon()


@pytest.fixture(scope="session")
def syllable_flag_strategy(weak_stress_lexicon) -> DefaultSyllableFlagStrategy:
    return DefaultSyllableFlagStrategy(weak_stress_lexicon=weak_stress_lexicon)


@pytest.fixture(scope="session")
def meter_canonicalizer() -> UkrainianMeterCanonicalizer:
    return UkrainianMeterCanonicalizer()


@pytest.fixture(scope="session")
def phonetic_transcriber() -> UkrainianIpaTranscriber:
    return UkrainianIpaTranscriber()


@pytest.fixture(scope="session")
def offline_embedder(_session_logger) -> OfflineDeterministicEmbedder:
    return OfflineDeterministicEmbedder(logger=_session_logger)


@pytest.fixture(scope="session")
def regeneration_prompt_builder():
    from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder

    return NumberedLinesRegenerationPromptBuilder()


@pytest.fixture(scope="session")
def mock_llm(regeneration_prompt_builder) -> MockLLMProvider:
    return MockLLMProvider(regeneration_prompt_builder=regeneration_prompt_builder)


@pytest.fixture(scope="session")
def demo_corpus() -> list[ThemeExcerpt]:
    return DemoThemeRepository().load()


@pytest.fixture(scope="session")
def retriever(offline_embedder) -> SemanticRetriever:
    return SemanticRetriever(offline_embedder)


@pytest.fixture(scope="session")
def feedback_formatter() -> IFeedbackFormatter:
    from src.infrastructure.feedback import UkrainianFeedbackFormatter

    return UkrainianFeedbackFormatter()
