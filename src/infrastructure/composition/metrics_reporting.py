"""Reporting composition — split out from ``metrics.py``.

Owns the reporter, results writers, tracer factory, HTTP error mapper,
and the evaluation aggregator. Everything post-run that turns metrics
into something a human or downstream tool reads.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import (
    IBatchResultsWriter,
    IEvaluationAggregator,
    IHttpErrorMapper,
    IReporter,
    IResultsWriter,
    ITracerFactory,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.evaluation import DefaultEvaluationAggregator
from src.infrastructure.http import DefaultHttpErrorMapper
from src.infrastructure.reporting import (
    CsvBatchResultsWriter,
    JsonResultsWriter,
    MarkdownReporter,
)
from src.infrastructure.tracing import PipelineTracerFactory

if TYPE_CHECKING:
    from src.composition_root import Container


class ReportingSubContainer:
    """Reporter, results writers, tracer factory, HTTP error mapper, aggregator."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def reporter(self) -> IReporter:
        def factory() -> IReporter:
            from src.domain.evaluation import ABLATION_CONFIGS

            cfg = self._parent.config
            provider = cfg.llm_provider or ("gemini" if cfg.gemini_api_key else "mock")
            model = cfg.gemini_model if provider == "gemini" else None
            descriptions = {
                c.label: c.description for c in ABLATION_CONFIGS if c.description
            }
            return MarkdownReporter(
                llm_provider=provider,
                llm_model=model,
                config_descriptions=descriptions,
                input_price_per_m=cfg.gemini_input_price_per_m,
                output_price_per_m=cfg.gemini_output_price_per_m,
            )

        return self._parent._get(CacheKey.REPORTER, factory)

    def results_writer(self) -> IResultsWriter:
        return self._parent._get(
            CacheKey.RESULTS_WRITER,
            lambda: JsonResultsWriter(reporter=self.reporter()),
        )

    def batch_results_writer(self) -> IBatchResultsWriter:
        return self._parent._get(
            CacheKey.BATCH_RESULTS_WRITER,
            CsvBatchResultsWriter,
        )

    def tracer_factory(self) -> ITracerFactory:
        return self._parent._get(CacheKey.TRACER_FACTORY, PipelineTracerFactory)

    def http_error_mapper(self) -> IHttpErrorMapper:
        return self._parent._get(CacheKey.HTTP_ERROR_MAPPER, DefaultHttpErrorMapper)

    def evaluation_aggregator(self) -> IEvaluationAggregator:
        return self._parent._get(
            CacheKey.EVALUATION_AGGREGATOR, DefaultEvaluationAggregator,
        )
