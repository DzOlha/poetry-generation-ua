from __future__ import annotations

import pytest

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
    Ablation configs from spec section 9:
    A: Baseline (pure LLM) — no retrieval, no validation, no feedback
    B: LLM + Validator — no retrieval, validation on, no feedback
    C: LLM + Val + Feedback — no retrieval, validation + feedback
    D: Full system — retrieval + validation + feedback
    E: No Retrieval — validation + feedback, no retrieval
    """

    def _make_llm(self) -> MockLLMClient:
        return MockLLMClient()

    def test_config_a_baseline_pure_llm(self):
        llm = self._make_llm()
        poem = llm.generate("тема: весна").text
        assert isinstance(poem, str)
        assert len(poem) > 0

    def test_config_b_llm_plus_validator(self, stress_dict: StressDict):
        llm = self._make_llm()
        poem = llm.generate("тема: весна").text
        report = check_poem(poem, "ямб", 4, "ABAB", stress_dict)
        assert isinstance(report, PipelineReport)
        assert isinstance(report.meter_accuracy, float)
        assert isinstance(report.rhyme_accuracy, float)

    def test_config_c_llm_val_feedback(self, stress_dict: StressDict, retriever: SemanticRetriever):
        poem, report = run_full_pipeline(
            theme="весна",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            corpus=[],
            llm=self._make_llm(),
            stress_dict=stress_dict,
            retriever=retriever,
            max_iterations=3,
        )
        assert isinstance(report, PipelineReport)

    def test_config_d_full_system(self, stress_dict: StressDict, retriever: SemanticRetriever):
        poem, report = run_full_pipeline(
            theme="весна у лісі",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            corpus=default_demo_corpus(),
            retriever=retriever,
            llm=self._make_llm(),
            stress_dict=stress_dict,
            max_iterations=3,
            top_k=3,
        )
        assert isinstance(poem, str)
        assert isinstance(report, PipelineReport)

    def test_config_e_no_retrieval(self, stress_dict: StressDict, retriever: SemanticRetriever):
        poem, report = run_full_pipeline(
            theme="самотність",
            meter="ямб",
            rhyme_scheme="ABAB",
            foot_count=4,
            corpus=[],
            llm=self._make_llm(),
            stress_dict=stress_dict,
            retriever=retriever,
            max_iterations=3,
        )
        assert isinstance(report, PipelineReport)

    def test_all_configs_produce_reports(self, stress_dict: StressDict, retriever: SemanticRetriever):
        reports: dict[str, PipelineReport | None] = {}

        # A: baseline
        llm_a = self._make_llm()
        poem_a = llm_a.generate("тема: весна").text
        reports["A"] = check_poem(poem_a, "ямб", 4, "ABAB", stress_dict)

        # B: llm + validator
        llm_b = self._make_llm()
        poem_b = llm_b.generate("тема: весна").text
        reports["B"] = check_poem(poem_b, "ямб", 4, "ABAB", stress_dict)

        # C: llm + val + feedback
        _, reports["C"] = run_full_pipeline(
            theme="весна", meter="ямб", rhyme_scheme="ABAB", foot_count=4,
            corpus=[], llm=self._make_llm(), stress_dict=stress_dict,
            retriever=retriever, max_iterations=3,
        )

        # D: full system
        _, reports["D"] = run_full_pipeline(
            theme="весна", meter="ямб", rhyme_scheme="ABAB", foot_count=4,
            corpus=default_demo_corpus(), retriever=retriever,
            llm=self._make_llm(), stress_dict=stress_dict, max_iterations=3,
        )

        # E: no retrieval
        _, reports["E"] = run_full_pipeline(
            theme="весна", meter="ямб", rhyme_scheme="ABAB", foot_count=4,
            corpus=[], llm=self._make_llm(), stress_dict=stress_dict,
            retriever=retriever, max_iterations=3,
        )

        for label, report in reports.items():
            assert report is not None, f"Config {label} produced no report"
            assert isinstance(report.meter_accuracy, float), f"Config {label}: meter_accuracy not float"
            assert isinstance(report.rhyme_accuracy, float), f"Config {label}: rhyme_accuracy not float"
