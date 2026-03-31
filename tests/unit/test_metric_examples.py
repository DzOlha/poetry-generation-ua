from __future__ import annotations

from pathlib import Path

import pytest

from src.retrieval.metric_examples import (
    MetricExample,
    find_metric_examples,
    load_metric_dataset,
)

# Path to the real corpus file (relative to project root, resolved at test run)
_DATASET_PATH = Path("corpus/ukrainian_poetry_dataset.json")


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _dataset_available() -> bool:
    return _DATASET_PATH.exists()


requires_dataset = pytest.mark.skipif(
    not _dataset_available(),
    reason="corpus/ukrainian_poetry_dataset.json not found",
)


# ---------------------------------------------------------------------------
# load_metric_dataset
# ---------------------------------------------------------------------------

class TestLoadMetricDataset:
    @requires_dataset
    def test_returns_list_of_metric_examples(self):
        examples = load_metric_dataset(_DATASET_PATH)
        assert isinstance(examples, list)
        assert len(examples) > 0

    @requires_dataset
    def test_all_items_are_metric_example(self):
        examples = load_metric_dataset(_DATASET_PATH)
        for ex in examples:
            assert isinstance(ex, MetricExample)

    @requires_dataset
    def test_known_shevchenko_poem_present(self):
        examples = load_metric_dataset(_DATASET_PATH)
        ids = {ex.id for ex in examples}
        assert "iamb_4_ABAB_shevchenko" in ids

    @requires_dataset
    def test_fields_populated(self):
        examples = load_metric_dataset(_DATASET_PATH)
        for ex in examples:
            assert ex.id != ""
            assert ex.meter != ""
            assert ex.feet > 0
            assert ex.scheme != ""
            assert ex.text != ""
            assert isinstance(ex.verified, bool)

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            load_metric_dataset(Path("nonexistent/path.json"))


# ---------------------------------------------------------------------------
# find_metric_examples — filtering
# ---------------------------------------------------------------------------

class TestFindMetricExamples:
    def test_returns_empty_for_missing_file(self):
        result = find_metric_examples("ямб", 4, "ABAB", dataset_path="no_such_file.json")
        assert result == []

    @requires_dataset
    def test_iamb_4_abab_returns_results(self):
        results = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH)
        assert len(results) > 0

    @requires_dataset
    def test_english_alias_iamb(self):
        """'iamb' alias should map to 'ямб' in the dataset."""
        results = find_metric_examples("iamb", 4, "ABAB", dataset_path=_DATASET_PATH)
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "ямб"

    @requires_dataset
    def test_english_alias_trochee(self):
        results = find_metric_examples("trochee", 4, "ABAB", dataset_path=_DATASET_PATH)
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "хорей"

    @requires_dataset
    def test_english_alias_dactyl(self):
        results = find_metric_examples("dactyl", 4, "AABB", dataset_path=_DATASET_PATH)
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "дактиль"

    @requires_dataset
    def test_english_alias_amphibrach(self):
        results = find_metric_examples("amphibrach", 4, "ABAB", dataset_path=_DATASET_PATH)
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "амфібрахій"

    @requires_dataset
    def test_english_alias_anapest(self):
        results = find_metric_examples("anapest", 3, "ABAB", dataset_path=_DATASET_PATH)
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "анапест"

    @requires_dataset
    def test_results_match_requested_feet(self):
        results = find_metric_examples("ямб", 5, "ABAB", dataset_path=_DATASET_PATH)
        for ex in results:
            assert ex.feet == 5

    @requires_dataset
    def test_results_match_requested_scheme(self):
        results = find_metric_examples("ямб", 4, "ABBA", dataset_path=_DATASET_PATH)
        for ex in results:
            assert ex.scheme.upper() == "ABBA"

    @requires_dataset
    def test_top_k_respected(self):
        results = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH, top_k=2)
        assert len(results) <= 2

    @requires_dataset
    def test_top_k_one(self):
        results = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH, top_k=1)
        assert len(results) == 1

    @requires_dataset
    def test_verified_first(self):
        """Verified examples should appear before unverified ones."""
        results = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH, top_k=10)
        verified_indices = [i for i, ex in enumerate(results) if ex.verified]
        unverified_indices = [i for i, ex in enumerate(results) if not ex.verified]
        if verified_indices and unverified_indices:
            assert max(verified_indices) < min(unverified_indices), (
                "Unverified example appears before a verified one"
            )

    @requires_dataset
    def test_verified_only_flag(self):
        results = find_metric_examples(
            "ямб", 4, "ABAB", dataset_path=_DATASET_PATH, verified_only=True
        )
        for ex in results:
            assert ex.verified is True

    @requires_dataset
    def test_no_match_returns_empty(self):
        results = find_metric_examples(
            "ямб", 99, "ZZZZ", dataset_path=_DATASET_PATH
        )
        assert results == []

    @requires_dataset
    def test_scheme_case_insensitive(self):
        results_upper = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH)
        results_lower = find_metric_examples("ямб", 4, "abab", dataset_path=_DATASET_PATH)
        assert len(results_upper) == len(results_lower)

    @requires_dataset
    def test_meter_case_insensitive(self):
        results_lower = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH)
        results_upper = find_metric_examples("ЯМБ", 4, "ABAB", dataset_path=_DATASET_PATH)
        assert len(results_lower) == len(results_upper)

    # ------------------------------------------------------------------
    # Content checks for specific known corpus entries
    # ------------------------------------------------------------------

    @requires_dataset
    def test_shevchenko_poem_retrievable(self):
        """Shevchenko's ямб 4ст ABAB poem must be retrievable."""
        results = find_metric_examples("ямб", 4, "ABAB", dataset_path=_DATASET_PATH, top_k=10)
        ids = {ex.id for ex in results}
        assert "iamb_4_ABAB_shevchenko" in ids, (
            "Shevchenko iamb_4_ABAB_shevchenko not found in retrieved examples"
        )

    @requires_dataset
    def test_lesya_anapest3_retrievable(self):
        """Леся Українка анапест 3ст ABAB poem must be retrievable."""
        results = find_metric_examples("анапест", 3, "ABAB", dataset_path=_DATASET_PATH, top_k=10)
        ids = {ex.id for ex in results}
        assert "anapest_3_ABAB_lesya" in ids, (
            "Lesya anapest_3_ABAB_lesya not found in retrieved examples"
        )

    @requires_dataset
    def test_sosyura_amphibrach4_retrievable(self):
        """Сосюра амфібрахій 4ст ABAB poem must be retrievable."""
        results = find_metric_examples("амфібрахій", 4, "ABAB", dataset_path=_DATASET_PATH, top_k=10)
        ids = {ex.id for ex in results}
        assert "amphibrach_4_ABAB_sosyura" in ids

    @requires_dataset
    def test_skovoroda_dactyl4_retrievable(self):
        """Сковорода дактиль 4ст AABB poem must be retrievable."""
        results = find_metric_examples("дактиль", 4, "AABB", dataset_path=_DATASET_PATH, top_k=10)
        ids = {ex.id for ex in results}
        assert "dactyl_4_AABB_skovoroda" in ids
