"""Batch evaluation runner — IRunner for the ablation-grid CSV script.

Thin wrapper around BatchEvaluationService: resolves scenarios (all / by
category / single), resolves ablation configs (all / single), wires the
service via the composition root, and writes one flat CSV row per run.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.composition_root import (
    build_batch_evaluation_service,
    build_container,
    build_logger,
)
from src.config import AppConfig
from src.domain.errors import DomainError, UnsupportedConfigError
from src.domain.evaluation import ABLATION_CONFIGS, AblationConfig, BatchRunRow
from src.domain.ports import ILogger, IRunner, IScenarioRegistry
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.infrastructure.reporting.csv_batch_results_writer import read_existing_runs
from src.services.batch_evaluation_service import BatchEvaluationService, CellKey


@dataclass
class BatchEvaluationRunnerConfig:
    """All parameters that control a single batch-evaluation run."""

    seeds: int = 3
    scenario_id: str | None = None
    category: str | None = None
    config_label: str | None = None
    corpus_path: str | None = None
    metric_examples_path: str | None = None
    metric_examples_top_k: int = 2
    max_iterations: int = 1
    output_path: str | None = None
    delay_between_calls_sec: float = 3.0
    # When True, ``output_path`` is read first; cells with a non-error
    # row are skipped this run and their old rows are preserved as-is in
    # the rewritten CSV. Use it to resume a batch that hit a daily quota
    # (e.g. Gemini 250 RPD) without paying the LLM bill twice.
    resume: bool = False
    # When True, scenarios with ``expected_to_succeed=False`` are dropped
    # before the matrix runs. Those scenarios (e.g. unsupported meter,
    # zero feet) intentionally crash the pipeline and produce error rows
    # that the analyzer already filters out — but they still burn LLM
    # quota and time. Skipping them up front keeps the batch lean.
    skip_degenerate: bool = False


class BatchEvaluationRunner(IRunner):
    """Runs the scenarios × configs × seeds matrix and writes runs.csv."""

    def __init__(
        self,
        app_config: AppConfig,
        config: BatchEvaluationRunnerConfig,
        logger: ILogger | None = None,
        service: BatchEvaluationService | None = None,
        scenario_registry: IScenarioRegistry | None = None,
        ablation_configs: list[AblationConfig] | None = None,
    ) -> None:
        self._app_config = app_config
        self._cfg = config
        self._logger: ILogger = logger or build_logger(app_config)
        self._ablation_configs = ablation_configs or list(ABLATION_CONFIGS)
        self._service = service
        if scenario_registry is None:
            scenario_registry = build_container(
                app_config, logger=self._logger,
            ).scenario_registry()
        self._scenarios: IScenarioRegistry = scenario_registry

    def run(self) -> int:
        cfg = self._cfg
        if cfg.seeds < 1:
            self._logger.error("seeds must be >= 1", seeds=cfg.seeds)
            return 1
        if not cfg.output_path:
            self._logger.error("output_path is required")
            return 1

        try:
            scenarios = self._resolve_scenarios(cfg)
        except DomainError as exc:
            self._logger.error("Scenario resolution failed", error=str(exc))
            return 1

        configs = self._resolve_configs(cfg)
        if not configs:
            self._logger.error("Unknown ablation config", label=cfg.config_label)
            return 1

        merged_config = self._override_config_paths(self._app_config, cfg)
        service = self._service or build_batch_evaluation_service(
            merged_config, logger=self._logger,
        )

        preserved_rows, skip_cells = self._load_resume_state(cfg)

        try:
            service.run(
                scenarios=scenarios,
                configs=configs,
                seeds=cfg.seeds,
                output_path=cfg.output_path,
                max_iterations=cfg.max_iterations,
                metric_examples_top_k=cfg.metric_examples_top_k,
                delay_between_calls_sec=cfg.delay_between_calls_sec,
                skip_cells=skip_cells,
                preserved_rows=preserved_rows,
            )
        except DomainError as exc:
            self._logger.error("Batch evaluation failed", error=str(exc))
            return 1

        return 0

    def _load_resume_state(
        self, cfg: BatchEvaluationRunnerConfig,
    ) -> tuple[tuple[BatchRunRow, ...], frozenset[CellKey]]:
        """Read existing runs.csv and pick out cells that succeeded.

        Returns ``((), frozenset())`` when ``cfg.resume`` is False or the
        file does not exist — i.e. this is a fresh batch. When resuming,
        rows with a non-empty ``error`` are dropped so they get re-run
        (a row 156 that died with RESOURCE_EXHAUSTED is exactly this
        case). The kept rows are passed through verbatim and their cell
        keys go into ``skip_cells`` so the iterator does not re-visit
        them.
        """
        if not cfg.resume or not cfg.output_path:
            return (), frozenset()
        existing = read_existing_runs(cfg.output_path)
        if not existing:
            self._logger.info(
                "Resume requested but no existing CSV; starting fresh",
                output=cfg.output_path,
            )
            return (), frozenset()
        kept = tuple(r for r in existing if not r.error)
        dropped = len(existing) - len(kept)
        skip = frozenset((r.scenario_id, r.config_label, r.seed) for r in kept)
        self._logger.info(
            "Resuming from existing CSV",
            preserved=len(kept),
            dropped_with_error=dropped,
            output=cfg.output_path,
        )
        return kept, skip

    # ------------------------------------------------------------------

    def _resolve_scenarios(
        self, cfg: BatchEvaluationRunnerConfig,
    ) -> tuple[EvaluationScenario, ...]:
        if cfg.scenario_id:
            s = self._scenarios.by_id(cfg.scenario_id.upper())
            if not s:
                available = [sc.id for sc in self._scenarios.all]
                raise UnsupportedConfigError(
                    f"Unknown scenario ID: {cfg.scenario_id}. Available: {available}",
                )
            scenarios: tuple[EvaluationScenario, ...] = (s,)
        elif cfg.category:
            scenarios = self._scenarios.by_category(ScenarioCategory(cfg.category))
        else:
            scenarios = self._scenarios.all

        if cfg.skip_degenerate:
            kept = tuple(s for s in scenarios if s.expected_to_succeed)
            dropped = len(scenarios) - len(kept)
            if dropped:
                self._logger.info(
                    "Skipping degenerate scenarios",
                    dropped=dropped,
                    ids=[s.id for s in scenarios if not s.expected_to_succeed],
                )
            scenarios = kept
        return scenarios

    def _resolve_configs(self, cfg: BatchEvaluationRunnerConfig) -> list[AblationConfig]:
        if cfg.config_label:
            return [c for c in self._ablation_configs if c.label == cfg.config_label.upper()]
        return list(self._ablation_configs)

    @staticmethod
    def _override_config_paths(
        base: AppConfig, cfg: BatchEvaluationRunnerConfig,
    ) -> AppConfig:
        from dataclasses import replace
        return replace(
            base,
            corpus_path=(
                Path(cfg.corpus_path) if cfg.corpus_path is not None else base.corpus_path
            ),
            metric_examples_path=(
                Path(cfg.metric_examples_path)
                if cfg.metric_examples_path is not None
                else base.metric_examples_path
            ),
        )
