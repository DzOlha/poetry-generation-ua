"""Pure unit tests for ``BatchEvaluationRunner``.

The audit flagged that the three high-level runners (generate, evaluation,
batch-evaluation) drive the user-facing entry points but only the first two
had unit coverage. This file exercises ``BatchEvaluationRunner`` with a
hand-written fake ``BatchEvaluationService`` so the runner's orchestration
contract is verified without spinning up the full container.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from src.config import AppConfig
from src.domain.errors import UnsupportedConfigError
from src.domain.evaluation import AblationConfig
from src.domain.ports import ILogger, IScenarioRegistry
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.runners.batch_evaluation_runner import (
    BatchEvaluationRunner,
    BatchEvaluationRunnerConfig,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

@dataclass
class _FakeBatchService:
    """Records the kwargs the runner passes through to the service."""

    raise_error: BaseException | None = None
    calls: list[dict[str, object]] = field(default_factory=list)

    def run(self, **kwargs: object) -> int:
        self.calls.append(kwargs)
        if self.raise_error is not None:
            raise self.raise_error
        return 0


@dataclass
class _CollectingLogger(ILogger):
    """Captures every structured log line for assertions."""

    records: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)

    def info(self, message: str, **fields: object) -> None:
        self.records.append(("info", message, dict(fields)))

    def warning(self, message: str, **fields: object) -> None:
        self.records.append(("warning", message, dict(fields)))

    def error(self, message: str, **fields: object) -> None:
        self.records.append(("error", message, dict(fields)))


class _StubRegistry(IScenarioRegistry):
    """Tuple-backed scenario registry — implementation of the port for tests."""

    def __init__(self, scenarios: Iterable[EvaluationScenario]) -> None:
        self._items = tuple(scenarios)
        self._by_id = {s.id: s for s in self._items}

    @property
    def all(self) -> tuple[EvaluationScenario, ...]:
        return self._items

    def by_id(self, scenario_id: str) -> EvaluationScenario | None:
        return self._by_id.get(scenario_id)

    def by_category(self, category: ScenarioCategory) -> tuple[EvaluationScenario, ...]:
        return tuple(s for s in self._items if s.category == category)


def _scen(
    sid: str,
    *,
    category: ScenarioCategory = ScenarioCategory.NORMAL,
    expected_to_succeed: bool = True,
) -> EvaluationScenario:
    return EvaluationScenario(
        id=sid, name=f"name-{sid}", category=category,
        theme="тест", meter="ямб", foot_count=4, rhyme_scheme="ABAB",
        expected_to_succeed=expected_to_succeed,
    )


_CFG_A = AblationConfig(label="A", enabled_stages=frozenset(), description="baseline")
_CFG_B = AblationConfig(label="B", enabled_stages=frozenset(), description="feedback")


def _make_runner(
    cfg: BatchEvaluationRunnerConfig,
    *,
    scenarios: tuple[EvaluationScenario, ...] = (_scen("N01"), _scen("N02")),
    service: _FakeBatchService | None = None,
    logger: _CollectingLogger | None = None,
) -> tuple[BatchEvaluationRunner, _FakeBatchService, _CollectingLogger]:
    fake_service = service or _FakeBatchService()
    fake_logger = logger or _CollectingLogger()
    runner = BatchEvaluationRunner(
        app_config=AppConfig.from_env(),
        config=cfg,
        logger=fake_logger,
        service=fake_service,  # type: ignore[arg-type]
        scenario_registry=_StubRegistry(scenarios),
        ablation_configs=[_CFG_A, _CFG_B],
    )
    return runner, fake_service, fake_logger


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------

class TestArgValidation:
    def test_seeds_below_one_returns_error_and_does_not_call_service(
        self, tmp_path: Path,
    ) -> None:
        runner, service, logger = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=0, output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 1
        assert service.calls == []
        assert any(msg == "seeds must be >= 1" for _, msg, _ in logger.records)

    def test_missing_output_path_returns_error(self) -> None:
        runner, service, logger = _make_runner(
            BatchEvaluationRunnerConfig(seeds=1, output_path=None),
        )
        assert runner.run() == 1
        assert service.calls == []
        assert any(msg == "output_path is required" for _, msg, _ in logger.records)

    def test_unknown_scenario_returns_error(self, tmp_path: Path) -> None:
        runner, service, logger = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1,
                scenario_id="ZZZZ",
                output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 1
        assert service.calls == []
        assert any(msg == "Scenario resolution failed" for _, msg, _ in logger.records)

    def test_unknown_config_label_returns_error(self, tmp_path: Path) -> None:
        runner, service, logger = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1,
                config_label="Z",
                output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 1
        assert service.calls == []
        assert any(msg == "Unknown ablation config" for _, msg, _ in logger.records)


# ---------------------------------------------------------------------------
# Successful orchestration
# ---------------------------------------------------------------------------

class TestRun:
    def test_runs_all_scenarios_when_neither_id_nor_category_given(
        self, tmp_path: Path,
    ) -> None:
        runner, service, _ = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1, output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 0
        assert len(service.calls) == 1
        scenarios = service.calls[0]["scenarios"]
        assert isinstance(scenarios, tuple)
        assert [s.id for s in scenarios] == ["N01", "N02"]

    def test_filters_to_single_scenario_id(self, tmp_path: Path) -> None:
        runner, service, _ = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=2,
                scenario_id="N01",
                output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 0
        scenarios = service.calls[0]["scenarios"]
        assert isinstance(scenarios, tuple)
        assert [s.id for s in scenarios] == ["N01"]

    def test_filters_to_single_config_label(self, tmp_path: Path) -> None:
        runner, service, _ = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1,
                config_label="b",  # case-insensitive
                output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 0
        configs = service.calls[0]["configs"]
        assert isinstance(configs, list)
        assert [c.label for c in configs] == ["B"]

    def test_skip_degenerate_drops_failing_scenarios(self, tmp_path: Path) -> None:
        runner, service, _ = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1,
                skip_degenerate=True,
                output_path=str(tmp_path / "runs.csv"),
            ),
            scenarios=(
                _scen("N01"),
                _scen("C04", category=ScenarioCategory.CORNER, expected_to_succeed=False),
                _scen("N02"),
            ),
        )
        assert runner.run() == 0
        scenarios = service.calls[0]["scenarios"]
        assert isinstance(scenarios, tuple)
        assert [s.id for s in scenarios] == ["N01", "N02"]

    def test_kwargs_are_forwarded_to_service(self, tmp_path: Path) -> None:
        runner, service, _ = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=4,
                max_iterations=2,
                metric_examples_top_k=3,
                delay_between_calls_sec=0.5,
                output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 0
        call = service.calls[0]
        assert call["seeds"] == 4
        assert call["max_iterations"] == 2
        assert call["metric_examples_top_k"] == 3
        assert call["delay_between_calls_sec"] == 0.5
        assert call["output_path"] == str(tmp_path / "runs.csv")


# ---------------------------------------------------------------------------
# Service errors
# ---------------------------------------------------------------------------

class TestServiceErrorHandling:
    def test_domain_error_from_service_returns_one(self, tmp_path: Path) -> None:
        runner, _, logger = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1, output_path=str(tmp_path / "runs.csv"),
            ),
            service=_FakeBatchService(
                raise_error=UnsupportedConfigError("bad meter"),
            ),
        )
        assert runner.run() == 1
        assert any(msg == "Batch evaluation failed" for _, msg, _ in logger.records)


# ---------------------------------------------------------------------------
# Resume — exercised separately so the happy-path stays focused.
# ---------------------------------------------------------------------------

class TestResume:
    def test_resume_off_passes_empty_skip_set(self, tmp_path: Path) -> None:
        runner, service, _ = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1,
                resume=False,
                output_path=str(tmp_path / "runs.csv"),
            ),
        )
        assert runner.run() == 0
        assert service.calls[0]["skip_cells"] == frozenset()
        assert service.calls[0]["preserved_rows"] == ()

    def test_resume_on_with_missing_file_starts_fresh(self, tmp_path: Path) -> None:
        runner, service, logger = _make_runner(
            BatchEvaluationRunnerConfig(
                seeds=1,
                resume=True,
                output_path=str(tmp_path / "missing.csv"),
            ),
        )
        assert runner.run() == 0
        assert service.calls[0]["skip_cells"] == frozenset()
        assert any(
            "Resume requested but no existing CSV" in msg
            for _, msg, _ in logger.records
        )


