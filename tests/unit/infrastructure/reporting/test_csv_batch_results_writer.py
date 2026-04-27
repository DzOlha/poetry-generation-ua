"""Tests for CsvBatchResultsWriter — write/read round-trip + resume support.

This is the source-of-truth file for ablation analysis (`runs.csv`).
A schema change here silently breaks `analyze_contributions.py` and the
`/ablation-report` dashboard, so we lock the format down here.
"""
from __future__ import annotations

from pathlib import Path

from src.domain.evaluation import BatchRunRow
from src.infrastructure.reporting.csv_batch_results_writer import (
    CsvBatchResultsWriter,
    read_existing_runs,
)


def _row(
    scenario_id: str = "N01",
    config_label: str = "E",
    seed: int = 0,
    meter_accuracy: float = 1.0,
    rhyme_accuracy: float = 0.5,
    num_iterations: int = 1,
    error: str | None = None,
    **overrides: object,
) -> BatchRunRow:
    base = {
        "scenario_id": scenario_id,
        "scenario_name": "spring scene",
        "category": "normal",
        "meter": "ямб",
        "foot_count": 4,
        "rhyme_scheme": "ABAB",
        "config_label": config_label,
        "config_description": "Full system",
        "seed": seed,
        "meter_accuracy": meter_accuracy,
        "rhyme_accuracy": rhyme_accuracy,
        "regeneration_success": 0.0,
        "semantic_relevance": 0.42,
        "num_iterations": num_iterations,
        "num_lines": 4,
        "duration_sec": 12.345,
        "input_tokens": 1500,
        "output_tokens": 800,
        "total_tokens": 2300,
        "estimated_cost_usd": 0.0123,
        "iteration_tokens": "it=0:in=750:out=400,it=1:in=750:out=400",
        "error": error,
    }
    base.update(overrides)
    return BatchRunRow(**base)  # type: ignore[arg-type]


class TestCsvWrite:
    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "deeply" / "runs.csv"
        writer = CsvBatchResultsWriter()
        n = writer.write(str(target), [_row()])
        assert target.exists()
        assert n == 1

    def test_returns_count_of_written_rows(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        writer = CsvBatchResultsWriter()
        n = writer.write(
            str(target),
            (_row(seed=s) for s in range(5)),  # iterable, not list
        )
        assert n == 5

    def test_header_matches_canonical_column_order(self, tmp_path: Path) -> None:
        # Lock the exact column order: analyze_contributions.py and the
        # ablation_report dashboard read columns by name from DictReader,
        # but tools that consume the CSV directly (Excel, pandas without
        # `usecols=...`) rely on positional order. Reordering would also
        # invalidate any existing batch_*/runs.csv on disk for resume.
        target = tmp_path / "runs.csv"
        CsvBatchResultsWriter().write(str(target), [])
        first_line = target.read_text(encoding="utf-8").splitlines()[0]
        actual_columns = first_line.split(",")
        expected_columns = [
            "scenario_id", "scenario_name", "category",
            "meter", "foot_count", "rhyme_scheme",
            "config_label", "config_description", "seed",
            "meter_accuracy", "rhyme_accuracy", "regeneration_success",
            "semantic_relevance", "num_iterations", "num_lines",
            "duration_sec", "input_tokens", "output_tokens", "total_tokens",
            "estimated_cost_usd", "iteration_tokens", "error",
        ]
        assert actual_columns == expected_columns

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        target.write_text("garbage\n", encoding="utf-8")
        CsvBatchResultsWriter().write(str(target), [_row()])
        # Old garbage replaced with valid header + one row.
        text = target.read_text(encoding="utf-8")
        assert "garbage" not in text
        assert "scenario_id" in text  # header
        assert "N01" in text          # data


class TestCsvRoundTrip:
    """Write rows then read them back; every field must survive intact."""

    def test_single_row_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        original = _row(
            scenario_id="N04", config_label="C", seed=2,
            meter_accuracy=0.875, rhyme_accuracy=0.5,
            num_iterations=2, num_lines=8,
            input_tokens=2000, output_tokens=1500,
            total_tokens=3500, estimated_cost_usd=0.0789,
        )
        CsvBatchResultsWriter().write(str(target), [original])
        rows = read_existing_runs(target)
        assert len(rows) == 1
        got = rows[0]
        # Spot-check every category of field.
        assert got.scenario_id == "N04"
        assert got.config_label == "C"
        assert got.seed == 2
        assert abs(got.meter_accuracy - 0.875) < 1e-6
        assert abs(got.rhyme_accuracy - 0.5) < 1e-6
        assert got.num_iterations == 2
        assert got.num_lines == 8
        assert got.input_tokens == 2000
        assert got.output_tokens == 1500
        assert got.total_tokens == 3500
        assert abs(got.estimated_cost_usd - 0.0789) < 1e-6
        assert got.error is None  # default empty → None

    def test_error_field_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        original = _row(error="LLMQuotaExceededError: 250/day")
        CsvBatchResultsWriter().write(str(target), [original])
        [got] = read_existing_runs(target)
        assert got.error == "LLMQuotaExceededError: 250/day"

    def test_many_rows_preserved_in_order(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        rows = [
            _row(scenario_id=f"N{i:02d}", seed=i % 3, config_label="ABCDE"[i % 5])
            for i in range(20)
        ]
        CsvBatchResultsWriter().write(str(target), rows)
        readback = read_existing_runs(target)
        assert len(readback) == 20
        for src, dst in zip(rows, readback, strict=True):
            assert dst.scenario_id == src.scenario_id
            assert dst.config_label == src.config_label
            assert dst.seed == src.seed


class TestReadExistingRunsResumeBehavior:
    def test_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        # Resume scenario: first run, file does not exist yet.
        assert read_existing_runs(tmp_path / "runs.csv") == []

    def test_corrupt_last_line_dropped_silently(self, tmp_path: Path) -> None:
        # Crash mid-write leaves a half-written line. The writer's docstring
        # promises we drop those rather than fail loudly — that lets the
        # runner re-execute just the missing cell on resume.
        target = tmp_path / "runs.csv"
        CsvBatchResultsWriter().write(str(target), [_row(seed=0), _row(seed=1)])
        with target.open("a", encoding="utf-8") as f:
            f.write("N99,partial,row,with,wrong\n")  # truncated row
        rows = read_existing_runs(target)
        assert len(rows) == 2  # both clean rows kept; junk dropped

    def test_row_with_non_int_seed_dropped(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        CsvBatchResultsWriter().write(str(target), [_row(seed=0)])
        # Manually append a row with a malformed seed to simulate manual
        # CSV editing gone wrong.
        with target.open("a", encoding="utf-8") as f:
            f.write(
                "N01,scenario,normal,ямб,4,ABAB,E,Full,not_a_number,"
                "1.0,1.0,0.0,0.5,1,4,1.0,0,0,0,0.0,,\n",
            )
        rows = read_existing_runs(target)
        assert len(rows) == 1  # malformed row dropped, valid one kept

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        target = tmp_path / "runs.csv"
        target.touch()
        assert read_existing_runs(target) == []

    def test_header_only_returns_empty_list(self, tmp_path: Path) -> None:
        # A clean file with header but no rows (e.g. crashed before any
        # cell completed). Resume should treat it as "start from scratch".
        target = tmp_path / "runs.csv"
        CsvBatchResultsWriter().write(str(target), [])
        assert read_existing_runs(target) == []
