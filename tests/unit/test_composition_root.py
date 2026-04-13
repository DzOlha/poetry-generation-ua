"""Smoke tests for the composition root.

Fast tests that build both services via `build_container` and assert that
the wire-up works: every previously-separate regression (missing port,
stale factory, circular dependency) first surfaces here.
"""
from __future__ import annotations

from dataclasses import replace as dc_replace

from src.composition_root import (
    build_container,
    build_evaluation_service,
    build_poetry_service,
)
from src.config import AppConfig
from src.infrastructure.llm.mock import MockLLMProvider
from src.infrastructure.logging import NullLogger
from src.infrastructure.prompts import NumberedLinesRegenerationPromptBuilder
from src.services.evaluation_service import EvaluationService
from src.services.poetry_service import PoetryService


def _offline_config() -> AppConfig:
    return dc_replace(AppConfig.from_env(), offline_embedder=True)


def _mock_llm() -> MockLLMProvider:
    return MockLLMProvider(regeneration_prompt_builder=NumberedLinesRegenerationPromptBuilder())


class TestBuildContainer:
    def test_returns_container_with_shared_adapters(self):
        container = build_container(_offline_config(), logger=NullLogger(), llm=_mock_llm())
        # Calling accessors twice returns the memoised instance.
        assert container.meter_validator() is container.meter_validator()
        assert container.rhyme_validator() is container.rhyme_validator()
        assert container.retriever() is container.retriever()

    def test_separate_containers_are_independent(self):
        """Two containers must not share cached instances."""
        c1 = build_container(_offline_config(), logger=NullLogger(), llm=_mock_llm())
        c2 = build_container(_offline_config(), logger=NullLogger(), llm=_mock_llm())
        assert c1.meter_validator() is not c2.meter_validator()
        assert c1.embedder() is not c2.embedder()

    def test_all_container_accessors_resolve(self):
        """Every public container method must resolve without error."""
        container = build_container(_offline_config(), logger=NullLogger(), llm=_mock_llm())
        accessors = [
            container.text_processor,
            container.stress_dict,
            container.syllable_counter,
            container.stress_resolver,
            container.phonetic_transcriber,
            container.meter_canonicalizer,
            container.meter_template_provider,
            container.weak_stress_lexicon,
            container.syllable_flag_strategy,
            container.prosody,
            container.line_feedback_builder,
            container.meter_validator,
            container.bsp_meter_validator,
            container.rhyme_scheme_extractor,
            container.rhyme_pair_analyzer,
            container.rhyme_validator,
            container.poem_validator,
            container.feedback_formatter,
            container.theme_repo,
            container.metric_repo,
            container.embedder,
            container.retriever,
            container.regeneration_prompt_builder,
            container.prompt_builder,
            container.regeneration_merger,
            container.iteration_stop_policy,
            container.llm_factory,
            container.llm,
            container.provider_info,
            container.feedback_cycle,
            container.feedback_iterator,
            container.skip_policy,
            container.stage_factory,
            container.generation_pipeline_inner,
            container.poem_generation_pipeline,
            container.metric_registry,
            container.final_metrics_stage,
            container.reporter,
            container.results_writer,
            container.tracer_factory,
            container.http_error_mapper,
            container.stage_record_builder,
            container.evaluation_aggregator,
            container.scenario_registry,
            container.evaluation_pipeline,
        ]
        for accessor in accessors:
            result = accessor()
            assert result is not None, f"{accessor.__name__}() returned None"


class TestBuildPoetryService:
    def test_built_with_container(self):
        cfg = _offline_config()
        container = build_container(cfg, logger=NullLogger(), llm=_mock_llm())
        svc = build_poetry_service(cfg, container=container)
        assert isinstance(svc, PoetryService)
        assert svc.llm_name == "MockLLMProvider"


class TestBuildEvaluationService:
    def test_built_with_container(self):
        cfg = _offline_config()
        container = build_container(cfg, logger=NullLogger(), llm=_mock_llm())
        svc = build_evaluation_service(cfg, container=container)
        assert isinstance(svc, EvaluationService)

    def test_shared_container_sharing(self):
        """One container → both services share every adapter (including the LLM)."""
        cfg = _offline_config()
        llm = _mock_llm()
        container = build_container(cfg, logger=NullLogger(), llm=llm)
        poetry = build_poetry_service(cfg, container=container)
        evaluation = build_evaluation_service(cfg, container=container)
        # Both services resolve to the same shared container; the LLM the
        # container exposes is the one wired everywhere (pipeline, iterator,
        # provider_info).
        assert container.llm() is llm
        assert poetry.llm_name == type(llm).__name__
        assert evaluation is not None
