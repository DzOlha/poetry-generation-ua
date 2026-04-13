"""Contract tests for every `IThemeRepository` implementation.

Each concrete adapter (`JsonThemeRepository`, `DemoThemeRepository`,
`InMemoryThemeRepository`) is exercised through the same test methods so
any new implementation automatically opts into the same behavioural
guarantees:

  - `load()` returns a list of `ThemeExcerpt`
  - successive calls return equal-value results (no mutation leak)
  - at least one excerpt exists for the adapter's "happy path"

Per-adapter I/O edge cases (missing file, malformed JSON) stay in the
adapter-specific test files — this module is strictly for the contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.domain.models import ThemeExcerpt
from src.domain.ports import IThemeRepository
from src.infrastructure.repositories.theme_repository import (
    DemoThemeRepository,
    InMemoryThemeRepository,
    JsonThemeRepository,
)

# ---------------------------------------------------------------------------
# Fixture factories — each repo type returns an adapter that has ≥1 excerpt
# ---------------------------------------------------------------------------

def _in_memory_repo() -> IThemeRepository:
    return InMemoryThemeRepository(
        [
            ThemeExcerpt(
                id="mem-1",
                text="рядок 1\nрядок 2",
                author="Автор",
                theme="весна",
            ),
        ]
    )


def _demo_repo() -> IThemeRepository:
    return DemoThemeRepository()


def _json_repo(tmp_path: Path) -> IThemeRepository:
    corpus = [
        {
            "id": "json-1",
            "text": "рядок 1\nрядок 2\nрядок 3",
            "author": "Автор",
            "approx_theme": "весна",
            "embedding": [0.1, 0.2, 0.3],
        }
    ]
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    return JsonThemeRepository(path=path)


# ---------------------------------------------------------------------------
# Parametrised contract
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=[
        pytest.param("in_memory", id="InMemoryThemeRepository"),
        pytest.param("demo", id="DemoThemeRepository"),
        pytest.param("json", id="JsonThemeRepository"),
    ],
)
def repository(request, tmp_path: Path) -> IThemeRepository:
    kind = request.param
    if kind == "in_memory":
        return _in_memory_repo()
    if kind == "demo":
        return _demo_repo()
    if kind == "json":
        return _json_repo(tmp_path)
    raise AssertionError(f"Unknown repo kind: {kind}")


class TestThemeRepositoryContract:
    def test_load_returns_list_of_theme_excerpts(self, repository: IThemeRepository) -> None:
        result = repository.load()
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(e, ThemeExcerpt) for e in result)

    def test_load_is_idempotent_value_equality(self, repository: IThemeRepository) -> None:
        first = repository.load()
        second = repository.load()
        assert first == second

    def test_load_does_not_return_same_mutable_reference(
        self, repository: IThemeRepository,
    ) -> None:
        # Consumers should be free to mutate the returned list without
        # affecting subsequent loads. (`DemoThemeRepository` and
        # `InMemoryThemeRepository` both copy; `JsonThemeRepository`
        # re-reads from disk so every call yields a fresh list.)
        first = repository.load()
        first.clear()
        second = repository.load()
        assert len(second) >= 1

    def test_excerpts_have_non_empty_text(self, repository: IThemeRepository) -> None:
        for excerpt in repository.load():
            assert excerpt.text != ""
            assert excerpt.id != ""


# ---------------------------------------------------------------------------
# Adapter-specific edge cases (not part of the shared contract)
# ---------------------------------------------------------------------------

class TestJsonThemeRepositoryEdgeCases:
    """I/O-specific failures that only apply to JsonThemeRepository."""

    def test_missing_file_raises_repository_error(self, tmp_path: Path) -> None:
        repo = JsonThemeRepository(path=tmp_path / "does_not_exist.json")
        from src.domain.errors import RepositoryError

        with pytest.raises(RepositoryError):
            repo.load()

    def test_malformed_json_raises_repository_error(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json at all {", encoding="utf-8")
        repo = JsonThemeRepository(path=path)
        from src.domain.errors import RepositoryError

        with pytest.raises(RepositoryError):
            repo.load()

    def test_embedding_field_parsed_as_tuple_of_floats(self, tmp_path: Path) -> None:
        data = [
            {
                "id": "x",
                "text": "text",
                "author": "a",
                "approx_theme": "t",
                "embedding": [1, 2.5, 3],
            }
        ]
        path = tmp_path / "c.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        repo = JsonThemeRepository(path=path)
        result = repo.load()
        assert result[0].embedding == (1.0, 2.5, 3.0)
        assert all(isinstance(x, float) for x in result[0].embedding)
