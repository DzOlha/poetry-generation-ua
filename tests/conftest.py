from __future__ import annotations

import pytest

from src.generation.llm import MockLLMClient
from src.meter.stress import StressDict
from src.retrieval.corpus import CorpusPoem, default_demo_corpus
from src.retrieval.retriever import SemanticRetriever


@pytest.fixture
def stress_dict() -> StressDict:
    return StressDict(on_ambiguity="first")


@pytest.fixture
def mock_llm() -> MockLLMClient:
    return MockLLMClient()


@pytest.fixture
def demo_corpus() -> list[CorpusPoem]:
    return default_demo_corpus()


@pytest.fixture
def retriever() -> SemanticRetriever:
    return SemanticRetriever()


SAMPLE_POEM_4LINES = (
    "Весна прийшла у ліс зелений,\n"
    "І спів пташок в гіллі бринить.\n"
    "Струмок біжить, мов шлях натхнений,\n"
    "І сонце крізь туман горить.\n"
)

SAMPLE_POEM_AABB = (
    "У полі вітер тихо грає,\n"
    "І колос спілий наливає.\n"
    "Блакитне небо понад нами,\n"
    "Вкрите білими хмарками.\n"
)
