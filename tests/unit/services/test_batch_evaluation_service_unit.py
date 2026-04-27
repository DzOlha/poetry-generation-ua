"""Pure unit tests for `BatchEvaluationService`.

Verifies orchestration only:
  - scenarios × configs × seeds iteration order
  - one BatchRunRow per run, fields propagate from scenario/config/trace
  - writer receives a streaming iterable (partial writes survive failures)
  - seeds < 1 is rejected
"""
from __future__ import annotations

from collections.abc import Iterable

import pytest

from src.domain.evaluation import (
    AblationConfig,
    BatchRunRow,
    IterationRecord,
    PipelineTrace,
)
from src.domain.ports import IBatchResultsWriter, IDelayer, ILogger
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.services.batch_evaluation_service import BatchEvaluationService


class NullLogger(ILogger):
    def info(self, message: str, **fields) -> None: ...
    def warning(self, message: str, **fields) -> None: ...
    def error(self, message: str, **fields) -> None: ...


class FakeDelayer(IDelayer):
    """Records sleeps without actually pausing — keeps tests fast."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)


class FakeBatchWriter(IBatchResultsWriter):
    """Collects every row the service emits, in order."""

    def __init__(self) -> None:
        self.rows: list[BatchRunRow] = []
        self.paths: list[str] = []

    def write(self, output_path: str, rows: Iterable[BatchRunRow]) -> int:
        self.paths.append(output_path)
        count = 0
        for row in rows:
            self.rows.append(row)
            count += 1
        return count


class FakeEvaluationService:
    """Stand-in for EvaluationService — records calls and returns canned traces."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run_scenario(
        self, scenario: EvaluationScenario, config: AblationConfig,
        *, max_iterations: int = 1, top_k: int = 5, metric_examples_top_k: int = 2,
    ) -> PipelineTrace:
        del max_iterations, top_k, metric_examples_top_k
        self.calls.append((scenario.id, config.label))
        return PipelineTrace(
            scenario_id=scenario.id,
            config_label=config.label,
            final_metrics={
                "meter_accuracy": 0.8,
                "rhyme_accuracy": 0.9,
                "regeneration_success": 0.15,
                "semantic_relevance": 0.72,
                "feedback_iterations": 2,
                "num_lines": 4,
                "input_tokens": 1500,
                "output_tokens": 300,
                "total_tokens": 1800,
                "estimated_cost_usd": 0.0066,
            },
            iterations=(
                IterationRecord(
                    iteration=0, poem_text="p", meter_accuracy=0.6,
                    rhyme_accuracy=0.7, feedback=(),
                    input_tokens=900, output_tokens=180,
                ),
                IterationRecord(
                    iteration=1, poem_text="p", meter_accuracy=0.8,
                    rhyme_accuracy=0.9, feedback=(),
                    input_tokens=600, output_tokens=120,
                ),
            ),
            total_duration_sec=0.5,
        )


def _scen(sid: str, *, name: str = "name", meter: str = "ямб",
          feet: int = 4, rhyme: str = "ABAB") -> EvaluationScenario:
    return EvaluationScenario(
        id=sid, name=name, category=ScenarioCategory.NORMAL,
        theme="тест", meter=meter, foot_count=feet, rhyme_scheme=rhyme,
    )


_CFG_A = AblationConfig(label="A", enabled_stages=frozenset(), description="baseline")
_CFG_B = AblationConfig(label="B", enabled_stages=frozenset(), description="feedback only")


@pytest.fixture
def service_and_doubles():
    eval_service = FakeEvaluationService()
    writer = FakeBatchWriter()
    service = BatchEvaluationService(
        evaluation_service=eval_service,  # type: ignore[arg-type]
        writer=writer,
        logger=NullLogger(),
        delayer=FakeDelayer(),
    )
    return service, eval_service, writer


class TestRun:
    def test_iterates_scenarios_configs_seeds_in_order(self, service_and_doubles) -> None:
        service, eval_service, _ = service_and_doubles
        service.run(
            scenarios=[_scen("N01"), _scen("N02")],
            configs=[_CFG_A, _CFG_B],
            seeds=2,
            output_path="/tmp/ignored.csv",
        )
        # Outer: scenario, middle: config, inner: seed -> 2·2·2 = 8 calls
        assert eval_service.calls == [
            ("N01", "A"), ("N01", "A"),
            ("N01", "B"), ("N01", "B"),
            ("N02", "A"), ("N02", "A"),
            ("N02", "B"), ("N02", "B"),
        ]

    def test_writes_one_row_per_call_with_seed_index(self, service_and_doubles) -> None:
        service, _, writer = service_and_doubles
        n = service.run(
            scenarios=[_scen("N01")],
            configs=[_CFG_A],
            seeds=3,
            output_path="/tmp/ignored.csv",
        )
        assert n == 3
        assert [(r.scenario_id, r.config_label, r.seed) for r in writer.rows] == [
            ("N01", "A", 0),
            ("N01", "A", 1),
            ("N01", "A", 2),
        ]

    def test_row_fields_propagate_from_scenario_config_trace(self, service_and_doubles) -> None:
        service, _, writer = service_and_doubles
        service.run(
            scenarios=[_scen("N01", name="Весна", meter="хорей", feet=3, rhyme="AABB")],
            configs=[_CFG_B],
            seeds=1,
            output_path="/tmp/ignored.csv",
        )
        row = writer.rows[0]
        assert row.scenario_id == "N01"
        assert row.scenario_name == "Весна"
        assert row.category == "normal"
        assert row.meter == "хорей"
        assert row.foot_count == 3
        assert row.rhyme_scheme == "AABB"
        assert row.config_label == "B"
        assert row.config_description == "feedback only"
        assert row.meter_accuracy == pytest.approx(0.8)
        assert row.rhyme_accuracy == pytest.approx(0.9)
        assert row.regeneration_success == pytest.approx(0.15)
        assert row.semantic_relevance == pytest.approx(0.72)
        assert row.num_iterations == 2
        assert row.input_tokens == 1500
        assert row.output_tokens == 300
        assert row.total_tokens == 1800
        assert row.estimated_cost_usd == pytest.approx(0.0066)
        assert row.iteration_tokens == "it=0:in=900:out=180,it=1:in=600:out=120"
        assert row.num_lines == 4
        assert row.duration_sec == pytest.approx(0.5)
        assert row.error is None

    def test_writer_receives_output_path(self, service_and_doubles) -> None:
        service, _, writer = service_and_doubles
        service.run(
            scenarios=[_scen("N01")],
            configs=[_CFG_A],
            seeds=1,
            output_path="/tmp/batch/runs.csv",
        )
        assert writer.paths == ["/tmp/batch/runs.csv"]

    def test_zero_seeds_raises(self, service_and_doubles) -> None:
        service, _, _ = service_and_doubles
        with pytest.raises(ValueError, match="seeds must be >= 1"):
            service.run(
                scenarios=[_scen("N01")],
                configs=[_CFG_A],
                seeds=0,
                output_path="/tmp/ignored.csv",
            )

    def test_streaming_writer_sees_partial_rows_if_service_fails_midway(self) -> None:
        """Writer must be able to receive rows incrementally — simulate a mid-stream crash."""

        class FlakyEvaluationService:
            def __init__(self) -> None:
                self.count = 0

            def run_scenario(self, scenario, config, **_kwargs):
                self.count += 1
                if self.count == 3:
                    raise RuntimeError("LLM timeout")
                return PipelineTrace(
                    scenario_id=scenario.id, config_label=config.label,
                    final_metrics={"meter_accuracy": 0.5, "rhyme_accuracy": 0.5,
                                   "feedback_iterations": 0, "num_lines": 4},
                )

        collected: list[BatchRunRow] = []

        class StreamingCollector(IBatchResultsWriter):
            def write(self, output_path: str, rows: Iterable[BatchRunRow]) -> int:
                del output_path
                count = 0
                for r in rows:
                    collected.append(r)
                    count += 1
                return count

        service = BatchEvaluationService(
            evaluation_service=FlakyEvaluationService(),  # type: ignore[arg-type]
            writer=StreamingCollector(),
            logger=NullLogger(),
            delayer=FakeDelayer(),
        )

        with pytest.raises(RuntimeError, match="LLM timeout"):
            service.run(
                scenarios=[_scen("N01"), _scen("N02")],
                configs=[_CFG_A],
                seeds=2,
                output_path="/tmp/ignored.csv",
            )

        # First 2 runs succeeded (N01, A, seed=0) and (N01, A, seed=1) before the crash.
        assert len(collected) == 2
        assert [(r.scenario_id, r.seed) for r in collected] == [("N01", 0), ("N01", 1)]
