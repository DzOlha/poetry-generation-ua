"""Tests for SequentialPipeline."""
from __future__ import annotations

from src.domain.evaluation import ABLATION_CONFIGS
from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme
from src.domain.pipeline_context import PipelineState
from src.domain.ports import IPipelineStage
from src.infrastructure.pipeline import SequentialPipeline
from src.infrastructure.tracing import PipelineTracer


class _RecordingStage(IPipelineStage):
    def __init__(self, name: str, log: list[str]) -> None:
        self._name = name
        self._log = log

    @property
    def name(self) -> str:
        return self._name

    def run(self, state: PipelineState) -> None:
        self._log.append(self._name)


def _make_state() -> PipelineState:
    config = ABLATION_CONFIGS[0]
    request = GenerationRequest(
        theme="весна у лісі",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
        max_iterations=1,
        top_k=2,
        metric_examples_top_k=1,
    )
    return PipelineState(
        request=request,
        config=config,
        tracer=PipelineTracer(scenario_id="N01", config_label=config.label),
    )


class TestSequentialPipeline:
    def test_runs_stages_in_order(self):
        log: list[str] = []
        stages: list[IPipelineStage] = [_RecordingStage(name=f"s{i}", log=log) for i in range(3)]
        final = _RecordingStage(name="final", log=log)
        SequentialPipeline(stages=stages, final_metrics_stage=final).run(_make_state())
        assert log == ["s0", "s1", "s2", "final"]

    def test_runs_final_metrics_even_after_abort(self):
        log: list[str] = []

        class _AbortingStage(IPipelineStage):
            @property
            def name(self) -> str:
                return "abort"

            def run(self, state: PipelineState) -> None:
                state.abort("boom")
                log.append("abort")

        final = _RecordingStage(name="final", log=log)
        SequentialPipeline(
            stages=[_AbortingStage()],
            final_metrics_stage=final,
        ).run(_make_state())
        assert log == ["abort", "final"]

    def test_final_metrics_optional_for_generation_pipelines(self):
        log: list[str] = []
        stages: list[IPipelineStage] = [_RecordingStage(name="only", log=log)]
        SequentialPipeline(stages=stages, final_metrics_stage=None).run(_make_state())
        assert log == ["only"]
