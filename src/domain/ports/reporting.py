"""Reporting ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.evaluation import BatchRunRow, EvaluationSummary, PipelineTrace


class IReporter(ABC):
    """Formats evaluation results into human-readable representations."""

    @abstractmethod
    def format_summary_table(self, summaries: list[EvaluationSummary]) -> str: ...

    @abstractmethod
    def format_trace_detail(self, trace: PipelineTrace) -> str: ...

    @abstractmethod
    def format_markdown_report(
        self,
        summaries: list[EvaluationSummary],
        traces: list[PipelineTrace],
    ) -> str: ...


class IResultsWriter(ABC):
    """Persists evaluation summaries + traces (JSON + Markdown) to disk."""

    @abstractmethod
    def write(
        self,
        output_path: str,
        summaries: list[EvaluationSummary],
        traces: list[PipelineTrace],
    ) -> None: ...


class IBatchResultsWriter(ABC):
    """Persists a stream of (scenario, config, seed) rows as a flat CSV.

    Implementations must flush after every row so that a crash mid-batch
    leaves a valid partial file — a 270-run job is expensive to re-run.
    """

    @abstractmethod
    def write(self, output_path: str, rows: Iterable[BatchRunRow]) -> int: ...
