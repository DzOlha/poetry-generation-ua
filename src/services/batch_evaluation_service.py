"""Batch evaluation service — wraps EvaluationService with seeds × configs × scenarios.

Produces a flat CSV (one row per run) for downstream component-contribution
analysis. Unlike EvaluationService which returns one PipelineTrace per
(scenario, config), this service repeats each cell `seeds` times and
streams rows through IBatchResultsWriter so a crash mid-batch does not
lose already-completed runs.

Seed is not plumbed into the LLM today (the provider's natural stochasticity
supplies variance between repeated runs). When deterministic seeding is
needed, extend GenerationRequest + LLM adapters and thread it through
EvaluationService._request_from_scenario.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import chain

from src.domain.evaluation import AblationConfig, BatchRunRow, PipelineTrace
from src.domain.ports import IBatchResultsWriter, IDelayer, ILogger
from src.domain.scenarios import EvaluationScenario
from src.services.evaluation_service import EvaluationService

# Identifies a single (scenario_id, config_label, seed) cell in the
# scenarios × configs × seeds matrix. Used by ``run`` to skip work that
# was already completed in a previous invocation.
CellKey = tuple[str, str, int]


class BatchEvaluationService:
    """Runs (scenario × config × seed) matrix and writes rows incrementally."""

    def __init__(
        self,
        evaluation_service: EvaluationService,
        writer: IBatchResultsWriter,
        logger: ILogger,
        delayer: IDelayer,
    ) -> None:
        self._eval = evaluation_service
        self._writer = writer
        self._logger = logger
        self._delayer = delayer

    def run(
        self,
        scenarios: Iterable[EvaluationScenario],
        configs: Iterable[AblationConfig],
        *,
        seeds: int,
        output_path: str,
        max_iterations: int = 1,
        metric_examples_top_k: int = 2,
        delay_between_calls_sec: float = 3.0,
        skip_cells: frozenset[CellKey] = frozenset(),
        preserved_rows: tuple[BatchRunRow, ...] = (),
    ) -> int:
        """Execute the full matrix and return number of rows written.

        ``skip_cells`` lists already-completed (scenario_id, config_label,
        seed) triples; the iterator silently passes them by, sparing the
        LLM call. ``preserved_rows`` are the corresponding rows from a
        previous run — they are written to the output file first so the
        final CSV is a complete picture (skipped + freshly-run rows),
        not just the cells executed in this invocation. Together they
        let the runner resume after a quota outage instead of paying
        the full bill twice.
        """
        if seeds < 1:
            raise ValueError(f"seeds must be >= 1, got {seeds}")

        scenarios_t = tuple(scenarios)
        configs_t = tuple(configs)
        total = len(scenarios_t) * len(configs_t) * seeds

        self._logger.info(
            "Starting batch evaluation",
            scenarios=len(scenarios_t),
            configs=len(configs_t),
            seeds=seeds,
            total_runs=total,
            preserved=len(preserved_rows),
            skip=len(skip_cells),
            output=output_path,
            delay_sec=delay_between_calls_sec,
        )

        new_rows = self._iter_rows(
            scenarios_t, configs_t, seeds,
            max_iterations=max_iterations,
            metric_examples_top_k=metric_examples_top_k,
            delay_between_calls_sec=delay_between_calls_sec,
            skip_cells=skip_cells,
        )
        written = self._writer.write(output_path, chain(preserved_rows, new_rows))

        self._logger.info("Batch evaluation complete", rows_written=written, output=output_path)
        return written

    # ------------------------------------------------------------------
    # Private — generator feeds the writer row by row so partial progress
    # is already on disk if the process dies.
    # ------------------------------------------------------------------

    def _iter_rows(
        self,
        scenarios: tuple[EvaluationScenario, ...],
        configs: tuple[AblationConfig, ...],
        seeds: int,
        *,
        max_iterations: int,
        metric_examples_top_k: int,
        delay_between_calls_sec: float,
        skip_cells: frozenset[CellKey] = frozenset(),
    ) -> Iterator[BatchRunRow]:
        total = len(scenarios) * len(configs) * seeds
        run_index = 0
        executed = 0
        for scenario in scenarios:
            for config in configs:
                for seed in range(seeds):
                    run_index += 1
                    if (scenario.id, config.label, seed) in skip_cells:
                        self._logger.info(
                            "batch run skipped (resume)",
                            progress=f"{run_index}/{total}",
                            scenario=scenario.id,
                            config=config.label,
                            seed=seed,
                        )
                        continue
                    if executed > 0 and delay_between_calls_sec > 0:
                        self._delayer.sleep(delay_between_calls_sec)
                    executed += 1
                    self._logger.info(
                        "batch run",
                        progress=f"{run_index}/{total}",
                        scenario=scenario.id,
                        config=config.label,
                        seed=seed,
                    )
                    trace = self._eval.run_scenario(
                        scenario, config,
                        max_iterations=max_iterations,
                        metric_examples_top_k=metric_examples_top_k,
                    )
                    yield _row_from_trace(trace, scenario, config, seed)


def _row_from_trace(
    trace: PipelineTrace,
    scenario: EvaluationScenario,
    config: AblationConfig,
    seed: int,
) -> BatchRunRow:
    fm = trace.final_metrics
    input_tokens = int(fm.get("input_tokens", 0))
    output_tokens = int(fm.get("output_tokens", 0))
    total_tokens = int(fm.get("total_tokens", input_tokens + output_tokens))
    return BatchRunRow(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        category=scenario.category.value,
        meter=scenario.meter,
        foot_count=scenario.foot_count,
        rhyme_scheme=scenario.rhyme_scheme,
        config_label=config.label,
        config_description=config.description,
        seed=seed,
        meter_accuracy=float(fm.get("meter_accuracy", 0.0)),
        rhyme_accuracy=float(fm.get("rhyme_accuracy", 0.0)),
        regeneration_success=float(fm.get("regeneration_success", 0.0)),
        semantic_relevance=float(fm.get("semantic_relevance", 0.0)),
        num_iterations=int(fm.get("feedback_iterations", 0)),
        num_lines=int(fm.get("num_lines", 0)),
        duration_sec=trace.total_duration_sec,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=float(fm.get("estimated_cost_usd", 0.0)),
        iteration_tokens=_format_iteration_tokens(trace),
        error=trace.error,
    )


def _format_iteration_tokens(trace: PipelineTrace) -> str:
    """Compact per-iteration `it=<i>:in=<n>:out=<n>` list, comma-separated.

    Empty string when no iterations carry token data — keeps CSV values
    terse for runs against mock adapters where everything is zeros.
    """
    parts = [
        f"it={it.iteration}:in={it.input_tokens}:out={it.output_tokens}"
        for it in trace.iterations
        if it.input_tokens or it.output_tokens
    ]
    return ",".join(parts)
