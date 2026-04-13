"""IResultsWriter implementation — persists evaluation output as JSON + Markdown.

Extracted out of `EvaluationRunner._save_results` so the runner stops doing
file I/O, JSON encoding and Markdown formatting itself. The writer depends
only on `IReporter` to produce the Markdown companion.
"""
from __future__ import annotations

import json
import os

from src.domain.evaluation import EvaluationSummary, PipelineTrace
from src.domain.ports import IReporter, IResultsWriter
from src.infrastructure.serialization import (
    evaluation_summary_to_dict,
    pipeline_trace_to_dict,
)


class JsonResultsWriter(IResultsWriter):
    """Writes summaries + traces to a JSON file plus a sibling Markdown report."""

    def __init__(self, reporter: IReporter) -> None:
        self._reporter = reporter

    def write(
        self,
        output_path: str,
        summaries: list[EvaluationSummary],
        traces: list[PipelineTrace],
    ) -> None:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        payload = {
            "summary": [evaluation_summary_to_dict(s) for s in summaries],
            "traces": [pipeline_trace_to_dict(t) for t in traces],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        md_path = os.path.splitext(output_path)[0] + ".md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._reporter.format_markdown_report(summaries, traces))
