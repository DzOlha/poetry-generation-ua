"""Tests for DefaultStageSkipPolicy."""
from __future__ import annotations

from src.domain.evaluation import ABLATION_CONFIGS
from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme
from src.domain.pipeline_context import PipelineState
from src.infrastructure.pipeline import DefaultStageSkipPolicy
from src.infrastructure.tracing import PipelineTracer


def _state(config_label: str) -> PipelineState:
    config = next(c for c in ABLATION_CONFIGS if c.label == config_label)
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


class TestDefaultStageSkipPolicy:
    def test_skip_when_aborted(self):
        policy = DefaultStageSkipPolicy()
        state = _state("E")
        state.abort("boom")
        assert policy.should_skip(state, "retrieval") is True

    def test_skip_when_ablation_disables_stage(self):
        policy = DefaultStageSkipPolicy()
        state = _state("A")
        assert policy.should_skip(state, "retrieval") is True
        assert policy.should_skip(state, "metric_examples") is True
        assert policy.should_skip(state, "feedback_loop") is True
        assert policy.should_skip(state, "validation") is False

    def test_non_togglable_stage_never_skipped_when_not_aborted(self):
        policy = DefaultStageSkipPolicy()
        state = _state("E")
        assert policy.should_skip(state, "prompt_construction") is False
        assert policy.should_skip(state, "initial_generation") is False

    def test_full_config_runs_everything(self):
        policy = DefaultStageSkipPolicy()
        state = _state("E")
        for stage in ("retrieval", "metric_examples", "validation", "feedback_loop"):
            assert policy.should_skip(state, stage) is False


class TestNoFeedbackAblationConfigs:
    """The F/G/H configs mirror C/D/E but with feedback_loop disabled,
    so paired-Δ vs. A measures the *raw* effect of an enrichment on the
    first draft (not masked by feedback iteratively repairing it)."""

    def test_f_runs_retrieval_validation_no_feedback(self):
        policy = DefaultStageSkipPolicy()
        state = _state("F")
        assert policy.should_skip(state, "retrieval") is False
        assert policy.should_skip(state, "validation") is False
        assert policy.should_skip(state, "metric_examples") is True
        assert policy.should_skip(state, "feedback_loop") is True

    def test_g_runs_metric_examples_validation_no_feedback(self):
        policy = DefaultStageSkipPolicy()
        state = _state("G")
        assert policy.should_skip(state, "metric_examples") is False
        assert policy.should_skip(state, "validation") is False
        assert policy.should_skip(state, "retrieval") is True
        assert policy.should_skip(state, "feedback_loop") is True

    def test_h_runs_both_enrichments_validation_no_feedback(self):
        policy = DefaultStageSkipPolicy()
        state = _state("H")
        assert policy.should_skip(state, "retrieval") is False
        assert policy.should_skip(state, "metric_examples") is False
        assert policy.should_skip(state, "validation") is False
        assert policy.should_skip(state, "feedback_loop") is True

    def test_all_eight_configs_present(self):
        labels = sorted(c.label for c in ABLATION_CONFIGS)
        assert labels == ["A", "B", "C", "D", "E", "F", "G", "H"]
