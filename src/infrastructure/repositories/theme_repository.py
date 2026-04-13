"""Theme repository implementations — loads poetry excerpts from various sources.

Hierarchy:
  IThemeRepository (port)
    ├── JsonThemeRepository     — loads from a JSON corpus file
    ├── DemoThemeRepository     — returns hard-coded demo excerpts (no file needed)
    └── InMemoryThemeRepository — wraps an in-memory list (for testing)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.domain.errors import RepositoryError
from src.domain.models import ThemeExcerpt
from src.domain.ports import IThemeRepository


class JsonThemeRepository(IThemeRepository):
    """Loads theme excerpts from a JSON corpus file.

    Expected JSON schema: list of objects with fields
    id, text, author, approx_theme (or theme), embedding.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def load(self) -> list[ThemeExcerpt]:
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as exc:
            raise RepositoryError(f"Theme corpus not found: {self._path}") from exc
        except json.JSONDecodeError as exc:
            raise RepositoryError(f"Theme corpus is not valid JSON: {self._path}") from exc
        return [self._from_dict(d) for d in data]

    @staticmethod
    def _from_dict(d: dict[str, Any]) -> ThemeExcerpt:
        raw_embedding = d.get("embedding", []) or []
        return ThemeExcerpt(
            id=d.get("id", ""),
            text=d.get("text", ""),
            author=d.get("author", ""),
            theme=d.get("approx_theme", d.get("theme", "")),
            embedding=tuple(float(x) for x in raw_embedding),
        )


class DemoThemeRepository(IThemeRepository):
    """Returns a minimal set of demo excerpts when no corpus file is available."""

    _DEMO: list[ThemeExcerpt] = [
        ThemeExcerpt(
            id="demo-1",
            text=(
                "Реве та стогне Дніпр широкий,\n"
                "Сердитий вітер завива,\n"
                "Додолу верби гне високі,\n"
                "Гори крутії рве, зрива."
            ),
            author="Тарас Шевченко",
            theme="природа, Дніпро",
        ),
        ThemeExcerpt(
            id="demo-2",
            text=(
                "Сонце заходить, гори чорніють,\n"
                "Пташечка тихне, поле німіє."
            ),
            author="Тарас Шевченко",
            theme="природа, вечір",
        ),
    ]

    def load(self) -> list[ThemeExcerpt]:
        return list(self._DEMO)


class InMemoryThemeRepository(IThemeRepository):
    """Wraps an in-memory list for unit testing."""

    def __init__(self, excerpts: list[ThemeExcerpt]) -> None:
        self._excerpts = list(excerpts)

    def load(self) -> list[ThemeExcerpt]:
        return list(self._excerpts)
