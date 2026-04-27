"""Evaluation service — runs scenarios through ablation configs via an IPipeline.

`EvaluationService` is a thin orchestrator. The stage chain lives behind
`IPipeline`; this class just builds a fresh tracer per run, assembles a
`PipelineState`, hands it to the pipeline, and reshapes the trace into an
`EvaluationSummary`. Scenario → request conversion happens here so the
fail-fast `MeterSpec.__post_init__` error for degenerate scenarios is
captured cleanly on the trace rather than crashing the stage chain.

`IScenarioRegistry` and the list of `AblationConfig`s are injected through
the constructor — the audit flagged the previous module-level import of
`SCENARIO_REGISTRY` / `ABLATION_CONFIGS` as a DIP leak (the service bypassed
its own port).
"""
from __future__ import annotations

from collections.abc import Iterable

from src.domain.errors import UnsupportedConfigError
from src.domain.evaluation import (
    AblationConfig,
    EvaluationSummary,
    PipelineTrace,
)
from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme
from src.domain.pipeline_context import PipelineState
from src.domain.ports import (
    IClock,
    ILogger,
    IPipeline,
    IScenarioRegistry,
    ITracerFactory,
)
from src.domain.scenarios import EvaluationScenario


class EvaluationService:
    """Runs evaluation scenarios through ablation configurations."""

    def __init__(
        self,
        pipeline: IPipeline,
        tracer_factory: ITracerFactory,
        logger: ILogger,
        scenario_registry: IScenarioRegistry,
        ablation_configs: Iterable[AblationConfig],
        clock: IClock,
    ) -> None:
        self._pipeline = pipeline
        self._tracer_factory = tracer_factory
        self._logger: ILogger = logger
        self._scenarios = scenario_registry
        self._ablation_configs: tuple[AblationConfig, ...] = tuple(ablation_configs)
        self._clock = clock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_scenario(
        self,
        scenario: EvaluationScenario,
        config: AblationConfig,
        *,
        max_iterations: int = 1,
        top_k: int = 5,
        metric_examples_top_k: int = 2,
    ) -> PipelineTrace:
        """Run a single scenario under one ablation config, returning a full trace."""
        tracer = self._tracer_factory.create(
            scenario_id=scenario.id, config_label=config.label,
        )

        try:
            request = self._request_from_scenario(
                scenario,
                max_iterations=max_iterations,
                top_k=top_k,
                metric_examples_top_k=metric_examples_top_k,
            )
        except UnsupportedConfigError as exc:
            # Degenerate scenario: meter or rhyme unsupported. Record it on
            # the trace without running any stage so the report still shows
            # the run as attempted.
            self._logger.warning(
                "scenario aborted before pipeline",
                scenario=scenario.id,
                error=str(exc),
            )
            tracer.set_error(str(exc))
            tracer.set_total_duration(0.0)
            return tracer.get_trace()

        state = PipelineState(
            request=request,
            config=config,
            tracer=tracer,
            scenario=scenario,
        )

        t_global = self._clock.now()
        self._pipeline.run(state)
        tracer.set_total_duration(self._clock.now() - t_global)
        return tracer.get_trace()

    def run_matrix(
        self,
        scenarios: list[EvaluationScenario] | None = None,
        configs: list[AblationConfig] | None = None,
        *,
        max_iterations: int = 1,
        metric_examples_top_k: int = 2,
    ) -> tuple[list[PipelineTrace], list[EvaluationSummary]]:
        """Run every scenario × config combination and return all traces and summaries."""
        scenarios = scenarios if scenarios is not None else list(self._scenarios.all)
        configs = configs if configs is not None else list(self._ablation_configs)

        traces: list[PipelineTrace] = []
        summaries: list[EvaluationSummary] = []

        for scenario in scenarios:
            for config in configs:
                trace = self.run_scenario(
                    scenario, config,
                    max_iterations=max_iterations,
                    metric_examples_top_k=metric_examples_top_k,
                )
                traces.append(trace)
                summaries.append(self._summary_from_trace(trace, scenario))

        return traces, summaries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _request_from_scenario(
        scenario: EvaluationScenario,
        *,
        max_iterations: int,
        top_k: int,
        metric_examples_top_k: int,
    ) -> GenerationRequest:
        return GenerationRequest(
            theme=scenario.theme,
            meter=MeterSpec(name=scenario.meter, foot_count=scenario.foot_count),
            rhyme=RhymeScheme(pattern=scenario.rhyme_scheme),
            structure=PoemStructure(
                stanza_count=scenario.stanza_count,
                lines_per_stanza=scenario.lines_per_stanza,
            ),
            max_iterations=max_iterations,
            top_k=top_k,
            metric_examples_top_k=metric_examples_top_k,
        )

    @staticmethod
    def _summary_from_trace(
        trace: PipelineTrace,
        scenario: EvaluationScenario,
    ) -> EvaluationSummary:
        fm = trace.final_metrics
        input_tokens = int(fm.get("input_tokens", 0))
        output_tokens = int(fm.get("output_tokens", 0))
        return EvaluationSummary(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            config_label=trace.config_label,
            meter=scenario.meter,
            foot_count=scenario.foot_count,
            rhyme_scheme=scenario.rhyme_scheme,
            meter_accuracy=fm.get("meter_accuracy", 0.0),
            rhyme_accuracy=fm.get("rhyme_accuracy", 0.0),
            num_iterations=int(fm.get("feedback_iterations", 0)),
            num_lines=int(fm.get("num_lines", 0)),
            duration_sec=trace.total_duration_sec,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=int(fm.get("total_tokens", input_tokens + output_tokens)),
            estimated_cost_usd=float(fm.get("estimated_cost_usd", 0.0)),
            error=trace.error,
        )
