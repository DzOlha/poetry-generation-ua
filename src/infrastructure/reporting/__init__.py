"""IReporter + IResultsWriter adapters."""
from src.infrastructure.reporting.json_results_writer import JsonResultsWriter
from src.infrastructure.reporting.markdown_reporter import MarkdownReporter

__all__ = ["JsonResultsWriter", "MarkdownReporter"]
