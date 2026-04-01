from __future__ import annotations

import pytest

from src.evaluation.runner import ABLATION_CONFIGS, run_traced_pipeline
from src.evaluation.scenarios import scenario_by_id
from src.evaluation.trace import PipelineTrace
from src.generation.llm import MockLLMClient
from src.meter.stress import StressDict
from src.pipeline.full_system import PipelineReport, check_poem, run_full_pipeline
from src.retrieval.corpus import CorpusPoem, default_demo_corpus
from src.retrieval.retriever import SemanticRetriever


@pytest.mark.integration
class TestCheckPoem:
    def test_returns_pipeline_report(self, stress_dict: StressDict):
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "Де тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\n"
            "І серце в тиші гомонить.\n"
        )
        report = check_poem(poem, "ямб", 4, "ABAB", stress_dict)
        assert isinstance(report, PipelineReport)
        assert isinstance(report.meter_ok, bool)
        assert isinstance(report.rhyme_ok, bool)
        assert 0.0 <= report.meter_accuracy <= 1.0
        assert 0.0 <= report.rhyme_accuracy <= 1.0
        assert isinstance(report.feedback, list)

    def test_empty_poem_is_valid(self, stress_dict: StressDict):
        report = check_poem("", "ямб", 4, "ABAB", stress_dict)
        assert report.meter_ok is True
        assert report.rhyme_ok is True


@pytest.mark.integration
class TestRunFullPipeline:
    def test_returns_poem_and_report(self, stress_dict: StressDict, retriever: SemanticRetriever):
        poem, report = run_full_pipeline(
            theme="весна у лісі",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            llm=MockLLMClient(),
            stress_dict=stress_dict,
            retriever=retriever,
            max_iterations=3,
        )
        assert isinstance(poem, str)
        assert len(poem) > 0
        assert isinstance(report, PipelineReport)
        assert report.iterations >= 0

    def test_feedback_loop_invokes_regeneration(self, stress_dict: StressDict, retriever: SemanticRetriever):
        mock = MockLLMClient()
        poem, report = run_full_pipeline(
            theme="весна у лісі",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            llm=mock,
            stress_dict=stress_dict,
            retriever=retriever,
            max_iterations=3,
        )
        assert mock.generate_calls == 1
        if not (report.meter_ok and report.rhyme_ok):
            assert mock.regenerate_calls > 0

    def test_max_iterations_respected(self, stress_dict: StressDict, retriever: SemanticRetriever):
        mock = MockLLMClient()
        poem, report = run_full_pipeline(
            theme="тема",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            llm=mock,
            stress_dict=stress_dict,
            retriever=retriever,
            max_iterations=2,
        )
        assert report.iterations <= 2

    def test_custom_corpus(self, stress_dict: StressDict, retriever: SemanticRetriever):
        corpus = [
            CorpusPoem(id="c1", text="тестовий вірш один\nрядок два\nрядок три\nрядок чотири\n"),
        ]
        poem, report = run_full_pipeline(
            theme="тест",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            corpus=corpus,
            llm=MockLLMClient(),
            stress_dict=stress_dict,
            retriever=retriever,
            max_iterations=1,
        )
        assert isinstance(poem, str)

    def test_pipeline_with_different_meters(self, stress_dict: StressDict, retriever: SemanticRetriever):
        for meter_name in ["ямб", "хорей", "дактиль", "амфібрахій", "анапест"]:
            poem, report = run_full_pipeline(
                theme="природа",
                meter=meter_name,
                rhyme_scheme="ABAB",
                foot_count=3,
                llm=MockLLMClient(),
                stress_dict=stress_dict,
                retriever=retriever,
                max_iterations=1,
            )
            assert isinstance(report, PipelineReport)

    def test_pipeline_with_different_rhyme_schemes(self, stress_dict: StressDict, retriever: SemanticRetriever):
        for scheme in ["AABB", "ABAB", "ABBA", "AAAA"]:
            poem, report = run_full_pipeline(
                theme="кохання",
                meter="ямб",
                rhyme_scheme=scheme,
                foot_count=4,
                llm=MockLLMClient(),
                stress_dict=stress_dict,
                retriever=retriever,
                max_iterations=1,
            )
            assert isinstance(report, PipelineReport)


@pytest.mark.integration
class TestAblationConfigurations:
    """
    Ablation configs (from src/evaluation/runner.py ABLATION_CONFIGS):
      A: Baseline (LLM + validator, no RAG, no feedback)            — validation only, no feedback loop
      B: LLM + Val + Feedback (no RAG)                             — validation + feedback, no retrieval
      C: Semantic RAG + Val + Feedback                              — semantic retrieval + validation + feedback
      D: Metric Examples + Val + Feedback                           — metric examples + validation + feedback, no semantic retrieval
      E: Full system (semantic + metric examples + val + feedback)  — all components active
    """

    def test_config_a_baseline(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """Config A: validates poem but does not run a feedback loop."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[0]  # A
        trace = run_traced_pipeline(
            scenario, config, llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        assert isinstance(trace, PipelineTrace)
        assert trace.config_label == "A"
        assert trace.final_metrics.get("meter_accuracy") is not None
        validation_stage = next(s for s in trace.stages if s.name == "validation")
        assert "SKIPPED" not in validation_stage.input_summary
        feedback_stage = next(s for s in trace.stages if s.name == "feedback_loop")
        assert "SKIPPED" in feedback_stage.input_summary

    def test_config_b_val_feedback(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """Config B: validation + feedback loop, no retrieval of any kind."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[1]  # B
        trace = run_traced_pipeline(
            scenario, config, llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever, max_iterations=2,
        )
        assert trace.config_label == "B"
        retrieval_stage = next(s for s in trace.stages if s.name == "retrieval")
        assert "SKIPPED" in retrieval_stage.input_summary
        metric_stage = next(s for s in trace.stages if s.name == "metric_examples")
        assert "SKIPPED" in metric_stage.input_summary
        feedback_stage = next(s for s in trace.stages if s.name == "feedback_loop")
        assert "SKIPPED" not in feedback_stage.input_summary

    def test_config_c_semantic_rag(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """Config C: semantic retrieval active, metric examples skipped."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[2]  # C
        trace = run_traced_pipeline(
            scenario, config, llm=MockLLMClient(), stress_dict=stress_dict,
            retriever=retriever, corpus=default_demo_corpus(),
        )
        assert trace.config_label == "C"
        retrieval_stage = next(s for s in trace.stages if s.name == "retrieval")
        assert "SKIPPED" not in retrieval_stage.input_summary
        metric_stage = next(s for s in trace.stages if s.name == "metric_examples")
        assert "SKIPPED" in metric_stage.input_summary

    def test_config_d_metric_examples(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """Config D: metric examples active, semantic retrieval skipped."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[3]  # D
        trace = run_traced_pipeline(
            scenario, config, llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever,
        )
        assert trace.config_label == "D"
        retrieval_stage = next(s for s in trace.stages if s.name == "retrieval")
        assert "SKIPPED" in retrieval_stage.input_summary
        metric_stage = next(s for s in trace.stages if s.name == "metric_examples")
        assert "SKIPPED" not in metric_stage.input_summary

    def test_config_e_full_system(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """Config E: all components active — semantic retrieval, metric examples, validation, feedback."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        config = ABLATION_CONFIGS[4]  # E
        trace = run_traced_pipeline(
            scenario, config, llm=MockLLMClient(), stress_dict=stress_dict,
            retriever=retriever, corpus=default_demo_corpus(),
        )
        assert trace.config_label == "E"
        retrieval_stage = next(s for s in trace.stages if s.name == "retrieval")
        assert "SKIPPED" not in retrieval_stage.input_summary
        metric_stage = next(s for s in trace.stages if s.name == "metric_examples")
        assert "SKIPPED" not in metric_stage.input_summary
        feedback_stage = next(s for s in trace.stages if s.name == "feedback_loop")
        assert "SKIPPED" not in feedback_stage.input_summary

    def test_all_configs_produce_metrics(self, stress_dict: StressDict, retriever: SemanticRetriever):
        """All 5 ablation configs must complete and expose meter_accuracy + rhyme_accuracy."""
        scenario = scenario_by_id("N01")
        assert scenario is not None
        corpus = default_demo_corpus()
        for config in ABLATION_CONFIGS:
            trace = run_traced_pipeline(
                scenario, config,
                llm=MockLLMClient(), stress_dict=stress_dict, retriever=retriever, corpus=corpus,
            )
            assert isinstance(trace, PipelineTrace), f"Config {config.label}: no trace returned"
            assert trace.final_metrics.get("meter_accuracy") is not None, f"Config {config.label}: missing meter_accuracy"
            assert trace.final_metrics.get("rhyme_accuracy") is not None, f"Config {config.label}: missing rhyme_accuracy"
