"""Integration tests for the evaluation harness: scenarios, traces, EvaluationService."""
from __future__ import annotations

from dataclasses import replace as dc_replace

import pytest

from src.composition_root import build_evaluation_service, build_reporter
from src.config import AppConfig
from src.domain.evaluation import ABLATION_CONFIGS, EvaluationSummary, PipelineTrace
from src.domain.values import ScenarioCategory
from src.infrastructure.evaluation.scenario_data import (
    ALL_SCENARIOS,
    CORNER_SCENARIOS,
    EDGE_SCENARIOS,
    NORMAL_SCENARIOS,
    SCENARIO_REGISTRY,
    scenario_by_id,
    scenarios_by_category,
)
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.logging import NullLogger
from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder
from src.services.evaluation_service import EvaluationService

# ---------------------------------------------------------------------------
# Scenario registry tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestScenarios:
    def test_all_scenarios_have_unique_ids(self):
        ids = [s.id for s in ALL_SCENARIOS]
        assert len(ids) == len(set(ids))

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

    def test_registry_all_tuple_length(self):
        assert len(SCENARIO_REGISTRY.all) == len(ALL_SCENARIOS)

    def test_registry_by_id(self):
        assert SCENARIO_REGISTRY.by_id("N01") is not None

    def test_build_request_returns_generation_request(self):
        from src.domain.models import GenerationRequest
        s = scenario_by_id("N01")
        assert s is not None
        req = s.build_request()
        assert isinstance(req, GenerationRequest)
        assert req.theme == s.theme

    def test_build_request_accepts_overrides(self):
        s = scenario_by_id("N01")
        assert s is not None
        req = s.build_request(stanza_count=2, lines_per_stanza=6)
        assert req.structure.stanza_count == 2
        assert req.structure.lines_per_stanza == 6

    def test_corner_expected_to_succeed_is_false(self):
        c04 = scenario_by_id("C04")
        assert c04 is not None
        assert c04.expected_to_succeed is False

    def test_c01_expected_to_succeed_is_true(self):
        c01 = scenario_by_id("C01")
        assert c01 is not None
        assert c01.expected_to_succeed is True


# ---------------------------------------------------------------------------
# EvaluationService — single scenario run
# ---------------------------------------------------------------------------

def _make_service() -> EvaluationService:
    cfg = dc_replace(AppConfig.from_env(), offline_embedder=True)
    llm = MockLLMProvider(regeneration_prompt_builder=NumberedLinesRegenerationPromptBuilder())
    return build_evaluation_service(cfg, logger=NullLogger(), llm=llm)


@pytest.fixture
def eval_service():
    return _make_service()


@pytest.mark.integration
class TestEvaluationServiceRunScenario:
    def test_config_a_baseline_trace(self, eval_service):
        scenario = scenario_by_id("N01")
        config = ABLATION_CONFIGS[0]  # A: baseline
        trace = eval_service.run_scenario(scenario, config)
        assert isinstance(trace, PipelineTrace)
        assert trace.scenario_id == "N01"
        assert trace.config_label == "A"
        assert trace.final_poem
        assert len(trace.stages) >= 4

    def test_config_c_semantic_rag_trace(self, eval_service):
        scenario = scenario_by_id("N01")
        config = ABLATION_CONFIGS[2]  # C
        trace = eval_service.run_scenario(scenario, config)
        assert trace.config_label == "C"
        assert any(s.name == "retrieval" for s in trace.stages)
        assert any(s.name == "validation" for s in trace.stages)
        assert any(s.name == "feedback_loop" for s in trace.stages)
        assert trace.final_metrics.get("meter_accuracy") is not None

    def test_config_e_full_system_trace(self, eval_service):
        scenario = scenario_by_id("N01")
        config = ABLATION_CONFIGS[4]  # E
        trace = eval_service.run_scenario(scenario, config)
        assert trace.config_label == "E"
        assert any(s.name == "retrieval" for s in trace.stages)
        assert any(s.name == "metric_examples" for s in trace.stages)

    def test_corner_empty_theme(self, eval_service):
        scenario = scenario_by_id("C01")
        config = ABLATION_CONFIGS[2]
        trace = eval_service.run_scenario(scenario, config)
        assert trace.error is None

    def test_corner_unsupported_meter(self, eval_service):
        # C04 uses meter "гекзаметр" — `MeterSpec.__post_init__` now fails fast,
        # so the service records the error on the trace and returns without
        # running any stage.
        scenario = scenario_by_id("C04")
        config = ABLATION_CONFIGS[2]
        trace = eval_service.run_scenario(scenario, config)
        assert isinstance(trace, PipelineTrace)
        assert trace.error is not None

    def test_trace_serialises_to_dict(self, eval_service):
        scenario = scenario_by_id("N01")
        config = ABLATION_CONFIGS[1]
        trace = eval_service.run_scenario(scenario, config)
        from src.infrastructure.serialization import pipeline_trace_to_dict

        d = pipeline_trace_to_dict(trace)
        assert "stages" in d
        assert "iterations" in d
        assert "final_metrics" in d

    def test_iterations_recorded_for_feedback(self, eval_service):
        scenario = scenario_by_id("N01")
        config = ABLATION_CONFIGS[1]
        trace = eval_service.run_scenario(scenario, config, max_iterations=3)
        assert len(trace.iterations) >= 1
        for it in trace.iterations:
            assert 0.0 <= it.meter_accuracy <= 1.0
            assert 0.0 <= it.rhyme_accuracy <= 1.0

    def test_no_duplicate_retrieval_stage_on_error(self, eval_service):
        # Config C uses retrieval; even if it runs successfully there must be
        # exactly one 'retrieval' stage (regression test for the old bug).
        scenario = scenario_by_id("N01")
        config = ABLATION_CONFIGS[2]
        trace = eval_service.run_scenario(scenario, config)
        names = [s.name for s in trace.stages]
        assert names.count("retrieval") == 1
        assert names.count("metric_examples") == 1


@pytest.mark.integration
class TestEvaluationMatrix:
    def test_small_matrix(self, eval_service):
        scenarios = [scenario_by_id("N01"), scenario_by_id("C01")]
        configs = [ABLATION_CONFIGS[0], ABLATION_CONFIGS[2]]
        traces, summaries = eval_service.run_matrix(scenarios=scenarios, configs=configs)
        assert len(traces) == 4
        assert len(summaries) == 4
        for s in summaries:
            assert isinstance(s, EvaluationSummary)

    def test_summary_table_format(self, eval_service):
        reporter = build_reporter()
        scenarios = [scenario_by_id("N01")]
        configs = [ABLATION_CONFIGS[0]]
        _, summaries = eval_service.run_matrix(scenarios=scenarios, configs=configs)
        table = reporter.format_summary_table(summaries)
        assert "Scenario" in table

    def test_trace_detail_format(self, eval_service):
        reporter = build_reporter()
        scenario = scenario_by_id("N01")
        trace = eval_service.run_scenario(scenario, ABLATION_CONFIGS[1])
        detail = reporter.format_trace_detail(trace)
        assert "Trace" in detail
        assert "scenario=N01" in detail

    def test_all_configs_produce_traces(self, eval_service):
        scenario = scenario_by_id("N01")
        traces, summaries = eval_service.run_matrix(
            scenarios=[scenario],
            configs=ABLATION_CONFIGS,
        )
        assert len(traces) == 5
        labels = {t.config_label for t in traces}
        assert labels == {"A", "B", "C", "D", "E"}
