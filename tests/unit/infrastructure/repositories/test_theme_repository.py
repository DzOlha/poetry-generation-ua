"""Unit tests for theme repository adapters (JSON/Demo/InMemory)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.domain.errors import RepositoryError
from src.domain.models import ThemeExcerpt
from src.infrastructure.repositories.theme_repository import (
    DemoThemeRepository,
    InMemoryThemeRepository,
    JsonThemeRepository,
)


class TestThemeExcerpt:
    def test_required_fields(self):
        excerpt = ThemeExcerpt(id="test_1", text="текст вірша", author="", theme="")
        assert excerpt.id == "test_1"
        # Embeddings are now tuples so the dataclass stays fully frozen.
        assert excerpt.embedding == ()

    def test_optional_fields(self):
        excerpt = ThemeExcerpt(
            id="test_2", text="текст", author="Автор", theme="природа",
            embedding=(0.1, 0.2),
        )
        assert excerpt.author == "Автор"
        assert excerpt.embedding == (0.1, 0.2)


class TestDemoThemeRepository:
    def test_load_returns_non_empty_list(self):
        assert len(DemoThemeRepository().load()) >= 2

    def test_each_excerpt_has_text(self):
        for ex in DemoThemeRepository().load():
            assert ex.text
            assert ex.id


class TestInMemoryThemeRepository:
    def test_returns_provided_excerpts(self):
        excerpts = [ThemeExcerpt(id="x", text="вірш", author="A", theme="t")]
        loaded = InMemoryThemeRepository(excerpts).load()
        assert len(loaded) == 1
        assert loaded[0].id == "x"


class TestJsonThemeRepository:
    def test_loads_valid_json(self):
        data = [
            {"id": "p1", "text": "вірш один", "author": "А1", "approx_theme": "природа"},
            {"id": "p2", "text": "вірш два"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            path = Path(f.name)
        excerpts = JsonThemeRepository(path).load()
        assert len(excerpts) == 2
        assert excerpts[0].id == "p1"
        assert excerpts[0].author == "А1"
        assert excerpts[1].author == ""
        path.unlink()

    def test_empty_corpus(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([], f)
            f.flush()
            path = Path(f.name)
        assert JsonThemeRepository(path).load() == []
        path.unlink()

    def test_load_from_nonexistent_raises(self, tmp_path):
        repo = JsonThemeRepository(tmp_path / "nonexistent.json")
        with pytest.raises(RepositoryError):
            repo.load()

    def test_load_valid_json_tmp_path(self, tmp_path):
        data = [{"id": "p1", "text": "вірш один", "author": "Автор", "approx_theme": "природа"}]
        corpus_file = tmp_path / "corpus.json"
        corpus_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        repo = JsonThemeRepository(corpus_file)
        excerpts = repo.load()
        assert excerpts[0].id == "p1"
        assert excerpts[0].author == "Автор"
