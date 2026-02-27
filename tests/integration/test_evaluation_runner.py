"""Integration tests for the evaluation harness: scenarios, traces, runner."""
from __future__ import annotations

import pytest

from src.evaluation.runner import (
    ABLATION_CONFIGS,
    AblationConfig,
    EvaluationSummary,
    format_summary_table,
    format_trace_detail,
    run_evaluation_matrix,
    run_traced_pipeline,
)
from src.evaluation.scenarios import (
    ALL_SCENARIOS,
    CORNER_SCENARIOS,
    EDGE_SCENARIOS,
    NORMAL_SCENARIOS,
    EvaluationScenario,
    ScenarioCategory,
    scenario_by_id,
    scenarios_by_category,
)
from src.evaluation.trace import PipelineTrace, StageRecord
from src.generation.llm import MockLLMClient
from src.meter.stress import StressDict
from src.retrieval.retriever import SemanticRetriever


# ---------------------------------------------------------------------------
# Scenario registry tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestScenarios:
    def test_all_scenarios_have_unique_ids(self):
        ids = [s.id for s in ALL_SCENARIOS]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"

    def test_scenario_counts(self):
        assert len(NORMAL_SCENARIOS) >= 3
        assert len(EDGE_SCENARIOS) >= 3
        assert len(CORNER_SCENARIOS) >= 3

    def test_lookup_by_id(self):
        s = scenario_by_id("N01")
        assert s is not None
        assert s.category == ScenarioCategory.NORMAL

    def test_lookup_unknown_returns_none(self):
        assert scenario_by_id("ZZZZZ") is None

    def test_filter_by_category(self):
        normal = scenarios_by_category(ScenarioCategory.NORMAL)
        assert all(s.category == ScenarioCategory.NORMAL for s in normal)
        assert len(normal) == len(NORMAL_SCENARIOS)


# ---------------------------------------------------------------------------
# Single traced run tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTracedPipeline:
    def test_config_a_baseline_trace(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[0]  # A: baseline
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        assert isinstance(trace, PipelineTrace)
        assert trace.scenario_id == "N01"
        assert trace.config_label == "A"
        assert trace.final_poem
        assert len(trace.stages) >= 3  # retrieval(skip), prompt, generation, validation(skip)
        assert trace.error is None

    def test_config_d_full_trace(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[3]  # D: full system
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        assert trace.config_label == "D"
        assert any(s.name == "retrieval" for s in trace.stages)
        assert any(s.name == "validation" for s in trace.stages)
        assert any(s.name == "feedback_loop" for s in trace.stages)
        assert trace.final_metrics.get("meter_accuracy") is not None
        assert trace.final_metrics.get("rhyme_accuracy") is not None

    def test_corner_empty_theme(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("C01")
        assert scenario is not None
        config = ABLATION_CONFIGS[3]  # D
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        assert trace.error is None  # should not crash

    def test_corner_unsupported_meter(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("C04")
        assert scenario is not None
        config = ABLATION_CONFIGS[3]  # D
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        # may produce validation error or zero accuracy — but must not crash
        assert isinstance(trace, PipelineTrace)

    def test_trace_serialises_to_dict(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[2]  # C
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        d = trace.to_dict()
        assert isinstance(d, dict)
        assert "stages" in d
        assert "iterations" in d
        assert "final_metrics" in d
        assert "scenario_id" in d

    def test_trace_contains_full_data(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[3]  # D: full system
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        d = trace.to_dict()
        for stage in d["stages"]:
            name = stage["stage"]
            if name == "prompt_construction":
                assert "input_data" in stage
                assert "output_data" in stage
                assert isinstance(stage["output_data"], str)
                assert len(stage["output_data"]) > 0
            elif name == "initial_generation":
                assert "input_data" in stage
                assert "output_data" in stage
                assert isinstance(stage["output_data"], str)
            elif name == "validation":
                if stage.get("input") != "SKIPPED (config.use_validation=False)":
                    assert "output_data" in stage
                    assert "meter_results" in stage["output_data"]
                    assert "rhyme_results" in stage["output_data"]
                    assert "feedback" in stage["output_data"]

    def test_iterations_recorded_for_feedback(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[2]  # C: feedback on
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
            max_iterations=3,
        )
        # iteration 0 is the initial check; further iterations if violations found
        assert len(trace.iterations) >= 1
        for it in trace.iterations:
            assert 0.0 <= it.meter_accuracy <= 1.0
            assert 0.0 <= it.rhyme_accuracy <= 1.0


# ---------------------------------------------------------------------------
# Evaluation matrix tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEvaluationMatrix:
    def test_small_matrix(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """Run 2 scenarios × 2 configs = 4 runs."""
        scenarios = [scenario_by_id("N01"), scenario_by_id("C01")]
        scenarios = [s for s in scenarios if s is not None]
        configs = [ABLATION_CONFIGS[0], ABLATION_CONFIGS[3]]  # A and D

        traces, summaries = run_evaluation_matrix(
            scenarios=scenarios,
            configs=configs,
            llm=MockLLMClient(),
            stress_dict=stress_dict,
            retriever=retriever,
        )
        assert len(traces) == 4
        assert len(summaries) == 4
        for s in summaries:
            assert isinstance(s, EvaluationSummary)
            assert 0.0 <= s.meter_accuracy <= 1.0
            assert 0.0 <= s.rhyme_accuracy <= 1.0

    def test_summary_table_format(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenarios = [scenario_by_id("N01")]
        scenarios = [s for s in scenarios if s is not None]
        configs = [ABLATION_CONFIGS[0]]

        _, summaries = run_evaluation_matrix(
            scenarios=scenarios, configs=configs,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        table = format_summary_table(summaries)
        assert "Scenario" in table
        assert "Config" in table
        assert "Meter%" in table

    def test_trace_detail_format(self, stress_dict: StressDict, retriever: SemanticRetriever):
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[2]
        trace = run_traced_pipeline(
            scenario, config,
            llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        detail = format_trace_detail(trace)
        assert "Trace" in detail
        assert "scenario=N01" in detail

    def test_all_configs_produce_traces(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """One scenario through all 5 ablation configs."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        traces, summaries = run_evaluation_matrix(
            scenarios=[scenario],
            configs=ABLATION_CONFIGS,
            llm=MockLLMClient(),
            stress_dict=stress_dict,
            retriever=retriever,
        )
        assert len(traces) == 5
        labels = {t.config_label for t in traces}
        assert labels == {"A", "B", "C", "D", "E"}
