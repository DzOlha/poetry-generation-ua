"""Evaluation runner — IRunner implementation for the evaluation matrix script."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from src.composition_root import (
    build_container,
    build_evaluation_service,
    build_logger,
    build_reporter,
    build_results_writer,
)
from src.config import AppConfig
from src.domain.errors import DomainError, UnsupportedConfigError
from src.domain.evaluation import ABLATION_CONFIGS, AblationConfig, EvaluationSummary
from src.domain.ports import (
    IEvaluationAggregator,
    ILogger,
    IReporter,
    IResultsWriter,
    IRunner,
    IScenarioRegistry,
)
from src.domain.scenarios import EvaluationScenario
from src.domain.values import ScenarioCategory
from src.services.evaluation_service import EvaluationService


@dataclass
class EvaluationRunnerConfig:
    """All parameters that control a single evaluation run.

    `corpus_path` and `metric_examples_path` default to `None` and are
    resolved against the `AppConfig` passed to the runner at run time.
    """

    scenario_id: str | None = None
    category: str | None = None
    config_label: str | None = None
    corpus_path: str | None = None
    metric_examples_path: str | None = None
    metric_examples_top_k: int = 2
    max_iterations: int = 1
    stanzas: int | None = None
    lines_per_stanza: int | None = None
    output_path: str | None = None
    verbose: bool = False


class EvaluationRunner(IRunner):
    """Runs the full scenario × ablation-config evaluation matrix."""

    def __init__(
        self,
        app_config: AppConfig,
        config: EvaluationRunnerConfig | None = None,
        logger: ILogger | None = None,
        reporter: IReporter | None = None,
        results_writer: IResultsWriter | None = None,
        service: EvaluationService | None = None,
        scenario_registry: IScenarioRegistry | None = None,
        aggregator: IEvaluationAggregator | None = None,
        ablation_configs: list[AblationConfig] | None = None,
    ) -> None:
        self._app_config = app_config
        self._cfg = config or EvaluationRunnerConfig()
        self._logger = logger or build_logger(app_config)
        self._reporter = reporter or build_reporter()
        self._results_writer = results_writer or build_results_writer(self._reporter)
        self._ablation_configs = ablation_configs or list(ABLATION_CONFIGS)
        self._service = service
        # Scenario registry and aggregator default to the production
        # container so that simple call sites stay ergonomic, but they
        # can be overridden for tests.
        if scenario_registry is None or aggregator is None:
            container = build_container(app_config, logger=self._logger)
            if scenario_registry is None:
                scenario_registry = container.scenario_registry()
            if aggregator is None:
                aggregator = container.evaluation_aggregator()
        self._scenarios: IScenarioRegistry = scenario_registry
        self._aggregator: IEvaluationAggregator = aggregator

    # ------------------------------------------------------------------
    # IRunner
    # ------------------------------------------------------------------

    def run(self) -> int:
        cfg = self._cfg
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
        service = self._service or build_evaluation_service(
            merged_config,
            logger=self._logger,
        )

        total = len(scenarios) * len(configs)
        self._logger.info(
            "Starting evaluation",
            scenarios=len(scenarios),
            configs=len(configs),
            total_runs=total,
            corpus=str(merged_config.corpus_path),
        )

        try:
            traces, summaries = service.run_matrix(
                scenarios=list(scenarios),
                configs=configs,
                max_iterations=cfg.max_iterations,
                metric_examples_top_k=cfg.metric_examples_top_k,
            )
        except DomainError as exc:
            self._logger.error("Evaluation matrix failed", error=str(exc))
            return 1

        if cfg.verbose:
            for trace in traces:
                for line in self._reporter.format_trace_detail(trace).splitlines():
                    self._logger.info(line)

        for line in self._reporter.format_summary_table(summaries).splitlines():
            self._logger.info(line)

        self._log_aggregates(summaries, configs, scenarios)

        if cfg.output_path:
            self._results_writer.write(cfg.output_path, summaries, traces)
            self._logger.info("Results saved", path=cfg.output_path)

        return 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_scenarios(
        self, cfg: EvaluationRunnerConfig,
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

        if cfg.stanzas is not None or cfg.lines_per_stanza is not None:
            scenarios = tuple(
                replace(
                    sc,
                    stanza_count=cfg.stanzas if cfg.stanzas is not None else sc.stanza_count,
                    lines_per_stanza=(
                        cfg.lines_per_stanza
                        if cfg.lines_per_stanza is not None
                        else sc.lines_per_stanza
                    ),
                )
                for sc in scenarios
            )
        return scenarios

    def _resolve_configs(self, cfg: EvaluationRunnerConfig) -> list[AblationConfig]:
        if cfg.config_label:
            return [c for c in self._ablation_configs if c.label == cfg.config_label.upper()]
        return list(self._ablation_configs)

    @staticmethod
    def _override_config_paths(
        base: AppConfig, cfg: EvaluationRunnerConfig,
    ) -> AppConfig:
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

    def _log_aggregates(
        self,
        summaries: list[EvaluationSummary],
        configs: list[AblationConfig],
        scenarios: tuple[EvaluationScenario, ...],
    ) -> None:
        """Delegate aggregation to `IEvaluationAggregator` and emit log lines.

        Pure logging; no arithmetic. The aggregator returns structured
        value objects which this method renders as info-level records.
        """
        aggregates = self._aggregator.aggregate(summaries, configs, scenarios)

        self._logger.info("--- AGGREGATE BY CONFIG ---")
        for cfg_agg in aggregates.by_config:
            self._logger.info(
                "config aggregate",
                config=cfg_agg.config_label,
                description=cfg_agg.description,
                meter=f"{cfg_agg.avg_meter_accuracy:.2%}",
                rhyme=f"{cfg_agg.avg_rhyme_accuracy:.2%}",
                iters=f"{cfg_agg.avg_iterations:.1f}",
                errors=f"{cfg_agg.error_count}/{cfg_agg.total_runs}",
            )

        self._logger.info("--- AGGREGATE BY CATEGORY ---")
        for cat_agg in aggregates.by_category:
            self._logger.info(
                "category aggregate",
                category=cat_agg.category,
                runs=cat_agg.total_runs,
                meter=f"{cat_agg.avg_meter_accuracy:.2%}",
                rhyme=f"{cat_agg.avg_rhyme_accuracy:.2%}",
                errors=cat_agg.error_count,
            )
