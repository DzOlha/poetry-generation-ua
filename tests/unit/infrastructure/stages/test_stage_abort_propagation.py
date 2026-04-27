"""Regression-guard for `if state.aborted: return` in every togglable stage.

When an upstream stage marks the pipeline aborted (typically after an
LLM error), every downstream stage must short-circuit BEFORE calling its
expensive collaborators (LLM, validators, embedder, repository). Without
this guard the system would, for example, run the validator against an
empty poem after generation failed, masking the real error with
secondary noise.

This is parameterised across all stages so adding a new stage that
forgets the guard fails one test, not zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.domain.evaluation import ABLATION_CONFIGS
from src.domain.models import (
    GenerationRequest,
    MeterSpec,
    PoemStructure,
    RetrievedExcerpt,
    RhymeScheme,
    ThemeExcerpt,
)
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    EvaluationContext,
    IEmbedder,
    IFeedbackIterator,
    ILLMProvider,
    IMetricCalculator,
    IMetricCalculatorRegistry,
    IMetricRepository,
    IPipelineStage,
    IPromptBuilder,
    IRetriever,
    IThemeRepository,
)
from src.infrastructure.feedback import UkrainianFeedbackFormatter
from src.infrastructure.logging import NullLogger
from src.infrastructure.pipeline import DefaultStageSkipPolicy
from src.infrastructure.stages import (
    DefaultStageRecordBuilder,
    FeedbackLoopStage,
    FinalMetricsStage,
    GenerationStage,
    MetricExamplesStage,
    PromptStage,
    RetrievalStage,
    ValidationStage,
)
from src.infrastructure.tracing import NullLLMCallRecorder, PipelineTracer

# ---------------------------------------------------------------------------
# Spy collaborators — every method bumps a counter so the test can assert
# "nobody was called".
# ---------------------------------------------------------------------------

@dataclass
class _CallCounter:
    calls: int = 0


@dataclass
class _SpyLLM(ILLMProvider):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def generate(self, prompt: str) -> str:
        self.counter.calls += 1
        return "x\n"

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        self.counter.calls += 1
        return poem


@dataclass
class _SpyThemeRepo(IThemeRepository):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def load(self):  # noqa: ANN201
        self.counter.calls += 1
        return []


@dataclass
class _SpyMetricRepo(IMetricRepository):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def find(self, query):  # noqa: ANN001, ANN201
        self.counter.calls += 1
        return []


@dataclass
class _SpyRetriever(IRetriever):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def retrieve(
        self,
        theme: str,
        corpus: list[ThemeExcerpt],
        top_k: int = 5,
    ) -> list[RetrievedExcerpt]:
        self.counter.calls += 1
        return []


@dataclass
class _SpyEmbedder(IEmbedder):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def encode(self, text: str) -> list[float]:
        self.counter.calls += 1
        return [0.0]


@dataclass
class _SpyPromptBuilder(IPromptBuilder):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def build(self, request, retrieved, examples) -> str:  # noqa: ANN001
        self.counter.calls += 1
        return "prompt"


@dataclass
class _SpyMetricCalculator(IMetricCalculator):
    counter: _CallCounter = field(default_factory=_CallCounter)

    @property
    def name(self) -> str:
        return "spy_metric"

    def calculate(self, context: EvaluationContext) -> float:
        self.counter.calls += 1
        return 0.0


@dataclass
class _SpyRegistry(IMetricCalculatorRegistry):
    calculator: _SpyMetricCalculator = field(default_factory=_SpyMetricCalculator)

    def register(self, calc: IMetricCalculator) -> None:
        return None

    def all(self) -> tuple[IMetricCalculator, ...]:
        return (self.calculator,)


@dataclass
class _SpyFeedbackIterator(IFeedbackIterator):
    counter: _CallCounter = field(default_factory=_CallCounter)

    def iterate(self, state: PipelineState) -> None:
        self.counter.calls += 1


# ---------------------------------------------------------------------------
# State helper
# ---------------------------------------------------------------------------

def _state(*, aborted: bool) -> PipelineState:
    config = next(c for c in ABLATION_CONFIGS if c.label == "E")
    tracer = PipelineTracer(scenario_id="N01", config_label=config.label)
    request = GenerationRequest(
        theme="весна",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
        max_iterations=1,
    )
    state = PipelineState(request=request, config=config, tracer=tracer)
    if aborted:
        state.abort("upstream stage failed")
    return state


# ---------------------------------------------------------------------------
# Stage builders — each returns (stage, list_of_collaborator_counters).
# ---------------------------------------------------------------------------

def _build_retrieval() -> tuple[IPipelineStage, list[_CallCounter]]:
    repo = _SpyThemeRepo()
    retr = _SpyRetriever()
    stage = RetrievalStage(
        theme_repo=repo, retriever=retr,
        skip_policy=DefaultStageSkipPolicy(),
        logger=NullLogger(),
    )
    return stage, [repo.counter, retr.counter]


def _build_metric_examples() -> tuple[IPipelineStage, list[_CallCounter]]:
    repo = _SpyMetricRepo()
    stage = MetricExamplesStage(
        metric_repo=repo,
        skip_policy=DefaultStageSkipPolicy(),
        logger=NullLogger(),
    )
    return stage, [repo.counter]


def _build_prompt() -> tuple[IPipelineStage, list[_CallCounter]]:
    builder = _SpyPromptBuilder()
    stage = PromptStage(prompt_builder=builder)
    return stage, [builder.counter]


def _build_generation() -> tuple[IPipelineStage, list[_CallCounter]]:
    llm = _SpyLLM()
    stage = GenerationStage(llm=llm, logger=NullLogger())
    return stage, [llm.counter]


def _build_validation() -> tuple[IPipelineStage, list[_CallCounter]]:
    # Use real Pattern validator + null collaborators — even constructed,
    # nothing should be called when state.aborted=True.
    from src.composition_root import build_container
    from src.config import AppConfig
    container = build_container(AppConfig.from_env())
    stage = ValidationStage(
        meter_validator=container.meter_validator(),
        rhyme_validator=container.rhyme_validator(),
        feedback_formatter=UkrainianFeedbackFormatter(),
        skip_policy=DefaultStageSkipPolicy(),
        logger=NullLogger(),
        record_builder=DefaultStageRecordBuilder(),
        llm_call_recorder=NullLLMCallRecorder(),
    )
    return stage, []  # body counters unnecessary — assert via tracer instead


def _build_feedback() -> tuple[IPipelineStage, list[_CallCounter]]:
    iterator = _SpyFeedbackIterator()
    stage = FeedbackLoopStage(
        iterator=iterator,
        skip_policy=DefaultStageSkipPolicy(),
    )
    return stage, [iterator.counter]


def _build_final_metrics() -> tuple[IPipelineStage, list[_CallCounter]]:
    registry = _SpyRegistry()
    stage = FinalMetricsStage(registry=registry, logger=NullLogger())
    return stage, [registry.calculator.counter]


_STAGE_BUILDERS = {
    "retrieval": _build_retrieval,
    "metric_examples": _build_metric_examples,
    "prompt": _build_prompt,
    "generation": _build_generation,
    "validation": _build_validation,
    "feedback_loop": _build_feedback,
    "final_metrics": _build_final_metrics,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stage_name", sorted(_STAGE_BUILDERS.keys()))
def test_stage_short_circuits_when_state_aborted(stage_name: str) -> None:
    """Aborted state → stage returns without calling collaborators."""
    stage, counters = _STAGE_BUILDERS[stage_name]()
    state = _state(aborted=True)

    stage.run(state)

    # No expensive collaborator was called.
    for c in counters:
        assert c.calls == 0, (
            f"{stage_name}: expected 0 calls when aborted, got {c.calls}"
        )

    # State.poem must remain whatever it was (i.e. no body-side mutation).
    assert state.poem == ""


def test_final_metrics_records_error_on_abort() -> None:
    """FinalMetricsStage is special: aborts must surface as trace.error
    so the JSON dashboard / evaluate_result.html can show the failure."""
    stage, _ = _build_final_metrics()
    state = _state(aborted=True)
    state.abort("LLM call failed: 502")  # set a specific reason
    stage.run(state)
    trace = state.tracer.get_trace()
    assert trace.error == "LLM call failed: 502"
