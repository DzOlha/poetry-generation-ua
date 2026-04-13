from __future__ import annotations

from pathlib import Path

import pytest

from src.config import AppConfig
from src.domain.models import MetricExample, MetricQuery
from src.infrastructure.meter import UkrainianMeterCanonicalizer
from src.infrastructure.repositories.metric_repository import JsonMetricRepository

_CANONICALIZER = UkrainianMeterCanonicalizer()


def _repo(path) -> JsonMetricRepository:
    return JsonMetricRepository(path=path, meter_canonicalizer=_CANONICALIZER)

# Path to the real corpus file — driven by METRIC_EXAMPLES_PATH env variable.
_DATASET_PATH = Path(AppConfig.from_env().metric_examples_path)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _dataset_available() -> bool:
    return _DATASET_PATH.exists()


requires_dataset = pytest.mark.skipif(
    not _dataset_available(),
    reason=f"Metric examples dataset not found at {_DATASET_PATH} ($METRIC_EXAMPLES_PATH)",
)


# ---------------------------------------------------------------------------
# JsonMetricRepository — loading
# ---------------------------------------------------------------------------

class TestLoadMetricDataset:
    @requires_dataset
    def test_returns_list_of_metric_examples(self):
        repo = _repo(_DATASET_PATH)
        examples = repo._load()
        assert isinstance(examples, list)
        assert len(examples) > 0

    @requires_dataset
    def test_all_items_are_metric_example(self):
        repo = _repo(_DATASET_PATH)
        for ex in repo._load():
            assert isinstance(ex, MetricExample)

    @requires_dataset
    def test_known_shevchenko_poem_present(self):
        repo = _repo(_DATASET_PATH)
        ids = {ex.id for ex in repo._load()}
        assert "iamb_4_ABAB_shevchenko" in ids

    @requires_dataset
    def test_fields_populated(self):
        repo = _repo(_DATASET_PATH)
        for ex in repo._load():
            assert ex.id != ""
            assert ex.meter != ""
            assert ex.feet > 0
            assert ex.scheme != ""
            assert ex.text != ""
            assert isinstance(ex.verified, bool)

    def test_nonexistent_path_raises(self):
        repo = _repo(Path("nonexistent/path.json"))
        with pytest.raises(Exception):
            repo._load()


# ---------------------------------------------------------------------------
# JsonMetricRepository — filtering via find()
# ---------------------------------------------------------------------------

class TestFindMetricExamples:
    def test_returns_empty_for_missing_file(self):
        from src.domain.errors import RepositoryError
        repo = _repo("no_such_file.json")
        with pytest.raises(RepositoryError):
            repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=5))

    @requires_dataset
    def test_iamb_4_abab_returns_results(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=10))
        assert len(results) > 0

    @requires_dataset
    def test_english_alias_iamb(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="iamb", feet=4, scheme="ABAB", top_k=10))
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "ямб"

    @requires_dataset
    def test_english_alias_trochee(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="trochee", feet=4, scheme="ABAB", top_k=10))
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "хорей"

    @requires_dataset
    def test_english_alias_dactyl(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="dactyl", feet=4, scheme="AABB", top_k=10))
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "дактиль"

    @requires_dataset
    def test_english_alias_amphibrach(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="amphibrach", feet=4, scheme="ABAB", top_k=10))
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "амфібрахій"

    @requires_dataset
    def test_english_alias_anapest(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="anapest", feet=3, scheme="ABAB", top_k=10))
        assert len(results) > 0
        for ex in results:
            assert ex.meter == "анапест"

    @requires_dataset
    def test_results_match_requested_feet(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=5, scheme="ABAB", top_k=10))
        for ex in results:
            assert ex.feet == 5

    @requires_dataset
    def test_results_match_requested_scheme(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABBA", top_k=10))
        for ex in results:
            assert ex.scheme.upper() == "ABBA"

    @requires_dataset
    def test_top_k_respected(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=2))
        assert len(results) <= 2

    @requires_dataset
    def test_top_k_one(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=1))
        assert len(results) == 1

    @requires_dataset
    def test_verified_first(self):
        """Verified examples should appear before unverified ones."""
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=10))
        verified_indices = [i for i, ex in enumerate(results) if ex.verified]
        unverified_indices = [i for i, ex in enumerate(results) if not ex.verified]
        if verified_indices and unverified_indices:
            assert max(verified_indices) < min(unverified_indices)

    @requires_dataset
    def test_verified_only_flag(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=10, verified_only=True))
        for ex in results:
            assert ex.verified is True

    @requires_dataset
    def test_no_match_returns_empty(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=99, scheme="ZZZZ", top_k=10))
        assert results == []

    @requires_dataset
    def test_scheme_case_insensitive(self):
        repo = _repo(_DATASET_PATH)
        results_upper = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=10))
        results_lower = repo.find(MetricQuery(meter="ямб", feet=4, scheme="abab", top_k=10))
        assert len(results_upper) == len(results_lower)

    @requires_dataset
    def test_meter_case_insensitive(self):
        repo = _repo(_DATASET_PATH)
        results_lower = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=10))
        results_upper = repo.find(MetricQuery(meter="ЯМБ", feet=4, scheme="ABAB", top_k=10))
        assert len(results_lower) == len(results_upper)

    @requires_dataset
    def test_shevchenko_poem_retrievable(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="ямб", feet=4, scheme="ABAB", top_k=10))
        ids = {ex.id for ex in results}
        assert "iamb_4_ABAB_shevchenko" in ids

    @requires_dataset
    def test_lesya_anapest3_retrievable(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="анапест", feet=3, scheme="ABAB", top_k=10))
        ids = {ex.id for ex in results}
        assert "anapest_3_ABAB_lesya" in ids

    @requires_dataset
    def test_sosyura_amphibrach4_retrievable(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="амфібрахій", feet=4, scheme="ABAB", top_k=10))
        ids = {ex.id for ex in results}
        assert "amphibrach_4_ABAB_sosyura" in ids

    @requires_dataset
    def test_skovoroda_dactyl4_retrievable(self):
        repo = _repo(_DATASET_PATH)
        results = repo.find(MetricQuery(meter="дактиль", feet=4, scheme="AABB", top_k=10))
        ids = {ex.id for ex in results}
        assert "dactyl_4_AABB_skovoroda" in ids
