"""Metric example repository — retrieves metrical reference poems."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.domain.errors import RepositoryError
from src.domain.models import MetricExample, MetricQuery
from src.domain.ports import IMeterCanonicalizer, IMetricRepository


def _parse_example(d: dict[str, Any]) -> MetricExample:
    return MetricExample(
        id=d.get("id", ""),
        meter=d.get("meter", ""),
        feet=int(d.get("feet", 0)),
        scheme=d.get("scheme", ""),
        text=d.get("text", ""),
        verified=bool(d.get("verified", False)),
        author=d.get("author", ""),
        note=d.get("note", ""),
    )


class JsonMetricRepository(IMetricRepository):
    """Loads metric examples from a JSON dataset file with in-memory caching.

    Meter-name canonicalisation is delegated to an injected
    `IMeterCanonicalizer` so adding new aliases or swapping languages no
    longer requires editing this repository.
    """

    def __init__(
        self,
        path: Path | str,
        meter_canonicalizer: IMeterCanonicalizer,
    ) -> None:
        self._path = Path(path)
        self._cache: list[MetricExample] | None = None
        self._canonicalizer = meter_canonicalizer

    def find(self, query: MetricQuery) -> list[MetricExample]:
        all_examples = self._load()
        target_meter = self._canonicalizer.canonicalize(query.meter)

        def matches(ex: MetricExample) -> bool:
            meter_ok = self._canonicalizer.canonicalize(ex.meter) == target_meter
            feet_ok = ex.feet == query.feet
            scheme_ok = ex.scheme.upper() == query.scheme.upper()
            verified_ok = (not query.verified_only) or ex.verified
            return meter_ok and feet_ok and scheme_ok and verified_ok

        results = [ex for ex in all_examples if matches(ex)]
        results.sort(key=lambda ex: (not ex.verified,))
        return results[: query.top_k]

    def _load(self) -> list[MetricExample]:
        if self._cache is None:
            try:
                with open(self._path, encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError as exc:
                raise RepositoryError(f"Metric examples not found: {self._path}") from exc
            except json.JSONDecodeError as exc:
                raise RepositoryError(f"Metric examples is not valid JSON: {self._path}") from exc
            self._cache = [_parse_example(d) for d in data]
        return self._cache
