"""Pure unit tests for `EvaluationService` — fakes pipeline and tracer.

These tests verify orchestration logic without running any real stage:
  - `run_scenario` degradation on UnsupportedConfigError
  - `run_matrix` iterates scenarios × configs in the expected order
  - `_request_from_scenario` propagates scenario fields correctly
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.evaluation import (
    AblationConfig,
    IterationRecord,
    PipelineTrace,
    StageRecord,
)
from src.domain.ports import (
    IClock,
    ILogger,
    IPipeline,
    IScenarioRegistry,
    ITracer,
    ITracerFactory,
)
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.services.evaluation_service import EvaluationService


class EmptyScenarioRegistry(IScenarioRegistry):
    """Minimal test double — the service only needs `all` for run_matrix defaults."""

    @property
    def all(self) -> tuple[EvaluationScenario, ...]:
        return ()

    def by_id(self, scenario_id: str) -> EvaluationScenario | None:
        return None

    def by_category(self, category: ScenarioCategory) -> tuple[EvaluationScenario, ...]:
        return ()

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeTracer(ITracer):
    def __init__(self, scenario_id: str, config_label: str) -> None:
        self._scenario_id = scenario_id
        self._config_label = config_label
        self._error: str | None = None
        self._duration: float = 0.0
        self._final_poem: str = ""
        self._stages: list[StageRecord] = []
        self._iterations: list[IterationRecord] = []
        self._final_metrics: dict[str, Any] = {}

    def add_stage(self, stage: StageRecord) -> None:
        self._stages.append(stage)

    def add_iteration(self, iteration: IterationRecord) -> None:
        self._iterations.append(iteration)

    def set_final_poem(self, poem: str) -> None:
        self._final_poem = poem

    def set_final_metrics(self, metrics: dict[str, Any]) -> None:
        self._final_metrics = dict(metrics)

    def set_total_duration(self, duration_sec: float) -> None:
        self._duration = duration_sec

    def set_error(self, error: str | None) -> None:
        self._error = error

    def iterations(self) -> tuple[IterationRecord, ...]:
        return tuple(self._iterations)

    def get_trace(self) -> PipelineTrace:
        return PipelineTrace(
            scenario_id=self._scenario_id,
            config_label=self._config_label,
            final_poem=self._final_poem,
            final_metrics={
                "meter_accuracy": 0.8,
                "rhyme_accuracy": 0.9,
                "feedback_iterations": 2,
                "num_lines": 4,
            },
            total_duration_sec=self._duration,
            error=self._error,
        )


class FakeTracerFactory(ITracerFactory):
    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []

    def create(self, scenario_id: str, config_label: str) -> ITracer:
        self.created.append((scenario_id, config_label))
        return FakeTracer(scenario_id, config_label)


@dataclass
class FakePipeline(IPipeline):
    runs: list[tuple[str | None, str]] = field(default_factory=list)
    set_poem: str = "згенерований вірш"

    def run(self, state) -> None:
        self.runs.append((state.scenario.id if state.scenario else None, state.config.label))
        state.poem = self.set_poem
        # Simulate tracer recording a final poem + metrics
        state.tracer.set_final_poem(self.set_poem)


class NullLogger(ILogger):
    def info(self, message: str, **fields) -> None: ...
    def warning(self, message: str, **fields) -> None: ...
    def error(self, message: str, **fields) -> None: ...


class FakeClock(IClock):
    """Monotonic stub that advances by a fixed step on each call."""

    def __init__(self, start: float = 0.0, step: float = 1.0) -> None:
        self._t = start
        self._step = step

    def now(self) -> float:
        t = self._t
        self._t += self._step
        return t


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _scen(
    sid: str,
    *,
    meter: str = "ямб",
    foot_count: int = 4,
    rhyme: str = "ABAB",
    category: ScenarioCategory = ScenarioCategory.NORMAL,
) -> EvaluationScenario:
    return EvaluationScenario(
        id=sid, name=f"n{sid}", category=category,
        theme="тест", meter=meter, foot_count=foot_count, rhyme_scheme=rhyme,
    )


_CFG_A = AblationConfig(label="A", enabled_stages=frozenset(), description="baseline")
_CFG_B = AblationConfig(label="B", enabled_stages=frozenset(), description="feedback")


@pytest.fixture
def service_and_doubles():
    pipeline = FakePipeline()
    tracer_factory = FakeTracerFactory()
    service = EvaluationService(
        pipeline=pipeline,
        tracer_factory=tracer_factory,
        logger=NullLogger(),
        scenario_registry=EmptyScenarioRegistry(),
        ablation_configs=(_CFG_A, _CFG_B),
        clock=FakeClock(),
    )
    return service, pipeline, tracer_factory


# ---------------------------------------------------------------------------
# run_scenario
# ---------------------------------------------------------------------------

class TestRunScenario:
    def test_creates_fresh_tracer_per_call(self, service_and_doubles) -> None:
        service, _, tracer_factory = service_and_doubles
        service.run_scenario(_scen("N01"), _CFG_A)
        service.run_scenario(_scen("N02"), _CFG_A)
        assert tracer_factory.created == [("N01", "A"), ("N02", "A")]

    def test_invokes_pipeline(self, service_and_doubles) -> None:
        service, pipeline, _ = service_and_doubles
        service.run_scenario(_scen("N01"), _CFG_A)
        assert pipeline.runs == [("N01", "A")]

    def test_unsupported_config_aborts_before_pipeline(self, service_and_doubles) -> None:
        service, pipeline, tracer_factory = service_and_doubles
        trace = service.run_scenario(_scen("C04", meter="гекзаметр"), _CFG_A)
        # No pipeline run because MeterSpec construction fails:
        assert pipeline.runs == []
        # Tracer still created and error recorded on the trace:
        assert tracer_factory.created == [("C04", "A")]
        assert trace.error is not None

    def test_returns_trace_with_configured_fields(self, service_and_doubles) -> None:
        service, _, _ = service_and_doubles
        trace = service.run_scenario(_scen("N01"), _CFG_A, max_iterations=5)
        assert trace.scenario_id == "N01"
        assert trace.config_label == "A"
        assert trace.final_poem == "згенерований вірш"


# ---------------------------------------------------------------------------
# run_matrix
# ---------------------------------------------------------------------------

class TestRunMatrix:
    def test_iterates_scenarios_cross_configs(self, service_and_doubles) -> None:
        service, pipeline, _ = service_and_doubles
        traces, summaries = service.run_matrix(
            scenarios=[_scen("N01"), _scen("N02")],
            configs=[_CFG_A, _CFG_B],
        )
        assert pipeline.runs == [
            ("N01", "A"), ("N01", "B"),
            ("N02", "A"), ("N02", "B"),
        ]
        assert len(traces) == 4
        assert len(summaries) == 4

    def test_summary_fields_propagate_from_trace(self, service_and_doubles) -> None:
        service, _, _ = service_and_doubles
        _, summaries = service.run_matrix(
            scenarios=[_scen("N01")],
            configs=[_CFG_A],
        )
        s = summaries[0]
        assert s.scenario_id == "N01"
        assert s.config_label == "A"
        # Values from FakeTracer.get_trace()'s final_metrics:
        assert s.meter_accuracy == 0.8
        assert s.rhyme_accuracy == 0.9
        assert s.num_iterations == 2
        assert s.num_lines == 4


# ---------------------------------------------------------------------------
# _request_from_scenario (private but critical mapping logic)
# ---------------------------------------------------------------------------

class TestRequestFromScenario:
    def test_preserves_scenario_fields(self) -> None:
        scen = _scen("N01", meter="хорей", foot_count=3, rhyme="AABB")
        req = EvaluationService._request_from_scenario(
            scen, max_iterations=7, top_k=11, metric_examples_top_k=5,
        )
        assert req.theme == "тест"
        assert req.meter.name == "хорей"
        assert req.meter.foot_count == 3
        assert req.rhyme.pattern == "AABB"
        assert req.max_iterations == 7
        assert req.top_k == 11
        assert req.metric_examples_top_k == 5
