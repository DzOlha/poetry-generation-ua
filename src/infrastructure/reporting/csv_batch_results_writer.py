"""IBatchResultsWriter implementation — flat CSV of batch run rows.

Every row is flushed to disk immediately so that a crash mid-batch leaves
a readable, valid partial file (re-running 270 LLM generations is expensive).
``read_existing_runs`` reverses the writer so the runner can resume a
half-finished batch instead of paying the LLM bill twice.
"""
from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from pathlib import Path

from src.domain.evaluation import BatchRunRow
from src.domain.ports import IBatchResultsWriter

_COLUMNS: tuple[str, ...] = (
    "scenario_id",
    "scenario_name",
    "category",
    "meter",
    "foot_count",
    "rhyme_scheme",
    "config_label",
    "config_description",
    "seed",
    "meter_accuracy",
    "rhyme_accuracy",
    "regeneration_success",
    "semantic_relevance",
    "num_iterations",
    "num_lines",
    "duration_sec",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost_usd",
    "iteration_tokens",
    "error",
)


class CsvBatchResultsWriter(IBatchResultsWriter):
    """Stream rows to a CSV file, flushing after every write."""

    def write(self, output_path: str, rows: Iterable[BatchRunRow]) -> int:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        count = 0
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_COLUMNS)
            writer.writeheader()
            f.flush()
            for row in rows:
                writer.writerow(_row_to_dict(row))
                f.flush()
                count += 1
        return count


def read_existing_runs(output_path: str | Path) -> list[BatchRunRow]:
    """Parse a previously-written runs.csv back into ``BatchRunRow``s.

    Returns an empty list when the file is missing — the runner uses that
    to distinguish "first run" from "resume". Rows whose required keys
    are missing or malformed are silently dropped: a corrupt last line
    after a crash is a likely cause and we prefer to re-run that one
    cell rather than fail loudly.
    """
    path = Path(output_path)
    if not path.is_file():
        return []
    rows: list[BatchRunRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            row = _row_from_dict(raw)
            if row is not None:
                rows.append(row)
    return rows


def _row_from_dict(raw: dict[str, str]) -> BatchRunRow | None:
    """Best-effort parse of a CSV row. Returns None on missing required keys."""
    try:
        return BatchRunRow(
            scenario_id=raw["scenario_id"],
            scenario_name=raw.get("scenario_name", ""),
            category=raw.get("category", ""),
            meter=raw.get("meter", ""),
            foot_count=int(raw.get("foot_count") or 0),
            rhyme_scheme=raw.get("rhyme_scheme", ""),
            config_label=raw["config_label"],
            config_description=raw.get("config_description", ""),
            seed=int(raw["seed"]),
            meter_accuracy=float(raw.get("meter_accuracy") or 0.0),
            rhyme_accuracy=float(raw.get("rhyme_accuracy") or 0.0),
            regeneration_success=float(raw.get("regeneration_success") or 0.0),
            semantic_relevance=float(raw.get("semantic_relevance") or 0.0),
            num_iterations=int(raw.get("num_iterations") or 0),
            num_lines=int(raw.get("num_lines") or 0),
            duration_sec=float(raw.get("duration_sec") or 0.0),
            input_tokens=int(raw.get("input_tokens") or 0),
            output_tokens=int(raw.get("output_tokens") or 0),
            total_tokens=int(raw.get("total_tokens") or 0),
            estimated_cost_usd=float(raw.get("estimated_cost_usd") or 0.0),
            iteration_tokens=raw.get("iteration_tokens", ""),
            error=(raw.get("error") or None) or None,
        )
    except (KeyError, ValueError):
        return None


def _row_to_dict(row: BatchRunRow) -> dict[str, object]:
    return {
        "scenario_id": row.scenario_id,
        "scenario_name": row.scenario_name,
        "category": row.category,
        "meter": row.meter,
        "foot_count": row.foot_count,
        "rhyme_scheme": row.rhyme_scheme,
        "config_label": row.config_label,
        "config_description": row.config_description,
        "seed": row.seed,
        "meter_accuracy": f"{row.meter_accuracy:.6f}",
        "rhyme_accuracy": f"{row.rhyme_accuracy:.6f}",
        "regeneration_success": f"{row.regeneration_success:.6f}",
        "semantic_relevance": f"{row.semantic_relevance:.6f}",
        "num_iterations": row.num_iterations,
        "num_lines": row.num_lines,
        "duration_sec": f"{row.duration_sec:.3f}",
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "total_tokens": row.total_tokens,
        "estimated_cost_usd": f"{row.estimated_cost_usd:.6f}",
        "iteration_tokens": row.iteration_tokens,
        "error": row.error or "",
    }
