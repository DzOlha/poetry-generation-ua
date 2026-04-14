"""Unit tests for individual IPipelineStage implementations."""
from __future__ import annotations

from src.domain.evaluation import ABLATION_CONFIGS
from src.domain.models import (
    GenerationRequest,
    MeterSpec,
    MetricExample,
    PoemStructure,
    RhymeScheme,
    ThemeExcerpt,
)
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    IEmbedder,
    ILLMProvider,
    IMetricRepository,
    IPromptBuilder,
    IThemeRepository,
)
from src.infrastructure.feedback import UkrainianFeedbackFormatter
from src.infrastructure.logging import NullLogger
from src.infrastructure.pipeline import DefaultStageSkipPolicy
from src.infrastructure.retrieval.semantic_retriever import SemanticRetriever
from src.infrastructure.stages import (
    DefaultStageRecordBuilder,
    FinalMetricsStage,
    GenerationStage,
    MetricExamplesStage,
    PromptStage,
    RetrievalStage,
    ValidationStage,
)
from src.infrastructure.tracing import PipelineTracer

_NULL_LOGGER = NullLogger()
_SKIP_POLICY = DefaultStageSkipPolicy()

# ---------------------------------------------------------------------------
# Fakes used across the stage tests (deterministic, no network)
# ---------------------------------------------------------------------------

class FakeEmbedder(IEmbedder):
    """Deterministic 2D embedding — order of the corpus determines similarity."""

    def encode(self, text: str) -> list[float]:
        return [float(len(text)), float(sum(ord(c) % 7 for c in text))]


class FakeThemeRepo(IThemeRepository):
    def __init__(self, items: list[ThemeExcerpt]) -> None:
        self._items = items

    def load(self) -> list[ThemeExcerpt]:
        return list(self._items)


class FakeMetricRepo(IMetricRepository):
    def __init__(self, items: list[MetricExample]) -> None:
        self._items = items

    def find(self, query):
        return list(self._items[: query.top_k])


class FakePromptBuilder(IPromptBuilder):
    def build(self, request, retrieved, examples) -> str:
        return f"prompt({request.theme}|{len(retrieved)}|{len(examples)})"


class FakeLLM(ILLMProvider):
    def __init__(
        self,
        response: str = "рядок один\nрядок два\nрядок три\nрядок чотири\n",
    ) -> None:
        self._response = response
        self.generate_calls = 0

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        return self._response

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return poem


# ---------------------------------------------------------------------------
# PipelineState helper
# ---------------------------------------------------------------------------

def _make_state(config_label: str = "E", max_iterations: int = 1) -> PipelineState:
    config = next(c for c in ABLATION_CONFIGS if c.label == config_label)
    tracer = PipelineTracer(scenario_id="N01", config_label=config.label)
    request = GenerationRequest(
        theme="весна у лісі, пробудження природи",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
        max_iterations=max_iterations,
        top_k=3,
        metric_examples_top_k=2,
    )
    return PipelineState(request=request, config=config, tracer=tracer)


# ---------------------------------------------------------------------------
# RetrievalStage
# ---------------------------------------------------------------------------

class TestRetrievalStage:
    def test_records_stage_even_when_skipped(self):
        state = _make_state("A")  # A has no retrieval enabled
        stage = RetrievalStage(
            theme_repo=FakeThemeRepo([]),
            retriever=SemanticRetriever(FakeEmbedder()),
            skip_policy=_SKIP_POLICY,
            logger=_NULL_LOGGER,
        )
        stage.run(state)
        stages = state.get_trace().stages
        assert len(stages) == 1
        assert stages[0].name == "retrieval"
        assert "SKIPPED" in stages[0].input_summary

    def test_records_retrieved_items(self):
        excerpts = [
            ThemeExcerpt(id="x", text="вірш весни", author="A", theme="природа"),
            ThemeExcerpt(id="y", text="вірш зими", author="B", theme="зима"),
        ]
        state = _make_state("E")
        stage = RetrievalStage(
            theme_repo=FakeThemeRepo(excerpts),
            retriever=SemanticRetriever(FakeEmbedder()),
            skip_policy=_SKIP_POLICY,
            logger=_NULL_LOGGER,
        )
        stage.run(state)
        stages = state.get_trace().stages
        assert stages[0].name == "retrieval"
        assert stages[0].error is None
        # Exactly one retrieval stage — regression guard.
        assert [s.name for s in stages].count("retrieval") == 1


# ---------------------------------------------------------------------------
# MetricExamplesStage
# ---------------------------------------------------------------------------

class TestMetricExamplesStage:
    def test_skipped_when_disabled(self):
        state = _make_state("A")  # A doesn't use metric examples
        stage = MetricExamplesStage(
            metric_repo=FakeMetricRepo([]),
            skip_policy=_SKIP_POLICY,
            logger=_NULL_LOGGER,
        )
        stage.run(state)
        stages = state.get_trace().stages
        assert stages[0].name == "metric_examples"
        assert "SKIPPED" in stages[0].input_summary

    def test_records_found_examples(self):
        state = _make_state("D")  # D enables metric examples
        example = MetricExample(
            id="e1", meter="ямб", feet=4, scheme="ABAB",
            text="рядок", verified=True,
        )
        stage = MetricExamplesStage(
            metric_repo=FakeMetricRepo([example]),
            skip_policy=_SKIP_POLICY,
            logger=_NULL_LOGGER,
        )
        stage.run(state)
        names = [s.name for s in state.get_trace().stages]
        assert names.count("metric_examples") == 1
        assert state.metric_examples[0].id == "e1"


# ---------------------------------------------------------------------------
# PromptStage
# ---------------------------------------------------------------------------

class TestPromptStage:
    def test_stores_prompt_on_state(self):
        state = _make_state("E")
        stage = PromptStage(prompt_builder=FakePromptBuilder())
        stage.run(state)
        assert state.prompt.startswith("prompt(")
        assert state.get_trace().stages[-1].name == "prompt_construction"


# ---------------------------------------------------------------------------
# GenerationStage
# ---------------------------------------------------------------------------

class TestGenerationStage:
    def test_writes_poem_to_state(self):
        state = _make_state("E")
        state.prompt = "prompt"
        llm = FakeLLM()
        GenerationStage(llm=llm, logger=_NULL_LOGGER).run(state)
        assert llm.generate_calls == 1
        assert state.poem.startswith("рядок")

    def test_strips_scansion_lines_from_llm_output(self):
        state = _make_state("E")
        state.prompt = "prompt"
        llm = FakeLLM(
            response=(
                "рядок перший звичайний,\n"
                "І-ДУТЬ у СЛАВ-ний БІЙ те-ПЕР но-ВІ пол-КИ.\n"
                "Слу(1) жи(2) ли(3) всі(4)\n"
                "1 2 3 4 5 6 7 8\n"
                "рядок останній нормальний.\n"
            )
        )
        GenerationStage(llm=llm, logger=_NULL_LOGGER).run(state)
        lines = [ln for ln in state.poem.splitlines() if ln.strip()]
        assert lines == [
            "рядок перший звичайний,",
            "рядок останній нормальний.",
        ]

    def test_falls_back_to_raw_when_sanitizer_empties_output(self):
        # If every line is scansion, sanitized result is empty — keep raw so
        # validation still sees something instead of silently vanishing.
        state = _make_state("E")
        state.prompt = "prompt"
        raw = "І-ДУТЬ у СЛАВ-ний БІЙ.\n1 2 3 4\n"
        llm = FakeLLM(response=raw)
        GenerationStage(llm=llm, logger=_NULL_LOGGER).run(state)
        assert state.poem == raw


# ---------------------------------------------------------------------------
# ValidationStage
# ---------------------------------------------------------------------------

class TestValidationStage:
    def test_populates_last_meter_and_rhyme(self, meter_validator, rhyme_validator):
        state = _make_state("E")
        state.poem = (
            "Весна прийшла у ліс зелений,\n"
            "І спів пташок в гіллі бринить.\n"
            "Струмок біжить, мов шлях натхнений,\n"
            "І сонце крізь туман горить.\n"
        )
        stage = ValidationStage(
            meter_validator=meter_validator,
            rhyme_validator=rhyme_validator,
            feedback_formatter=UkrainianFeedbackFormatter(),
            skip_policy=_SKIP_POLICY,
            logger=_NULL_LOGGER,
            record_builder=DefaultStageRecordBuilder(),
        )
        stage.run(state)
        assert state.last_meter_result is not None
        assert state.last_rhyme_result is not None
        assert state.get_trace().iterations, "iteration 0 should be recorded"


# ---------------------------------------------------------------------------
# FinalMetricsStage
# ---------------------------------------------------------------------------

class TestFinalMetricsStage:
    def test_populates_final_metrics(self, meter_validator, rhyme_validator):
        from src.infrastructure.metrics import (
            DefaultMetricCalculatorRegistry,
            LineCountCalculator,
            MeterAccuracyCalculator,
            RhymeAccuracyCalculator,
        )
        state = _make_state("E")
        state.poem = "рядок один\nрядок два\n"
        registry = DefaultMetricCalculatorRegistry()
        registry.register(MeterAccuracyCalculator(meter_validator=meter_validator))
        registry.register(RhymeAccuracyCalculator(rhyme_validator=rhyme_validator))
        registry.register(LineCountCalculator())
        stage = FinalMetricsStage(
            registry=registry,
            logger=_NULL_LOGGER,
        )
        stage.run(state)
        trace = state.get_trace()
        assert "meter_accuracy" in trace.final_metrics
        assert "rhyme_accuracy" in trace.final_metrics
        assert trace.final_metrics["num_lines"] == 2
        assert trace.final_poem == state.poem
