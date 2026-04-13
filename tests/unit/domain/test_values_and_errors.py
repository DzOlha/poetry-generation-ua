"""Tests for domain enums and error hierarchy."""
from __future__ import annotations

import pytest

from src.domain.errors import (
    DomainError,
    LLMError,
    RepositoryError,
    UnsupportedConfigError,
)
from src.domain.values import MeterName, RhymePattern, ScenarioCategory


class TestMeterName:
    def test_parses_ukrainian(self):
        assert MeterName.parse("ямб") == MeterName.IAMB

    def test_parses_english_alias(self):
        assert MeterName.parse("iamb") == MeterName.IAMB_EN

    def test_case_insensitive(self):
        assert MeterName.parse("ЯМБ") == MeterName.IAMB

    def test_unknown_raises(self):
        with pytest.raises(UnsupportedConfigError):
            MeterName.parse("гекзаметр")

    def test_canonical_collapses_english(self):
        assert MeterName.IAMB_EN.canonical() == MeterName.IAMB
        assert MeterName.TROCHEE_EN.canonical() == MeterName.TROCHEE
        assert MeterName.IAMB.canonical() == MeterName.IAMB


class TestRhymePattern:
    def test_parses_valid(self):
        assert RhymePattern.parse("ABAB") == RhymePattern.ABAB
        assert RhymePattern.parse("aabb") == RhymePattern.AABB

    def test_unknown_raises(self):
        with pytest.raises(UnsupportedConfigError):
            RhymePattern.parse("XYZW")


class TestScenarioCategory:
    def test_enum_values(self):
        assert ScenarioCategory.NORMAL.value == "normal"
        assert ScenarioCategory.EDGE.value == "edge"
        assert ScenarioCategory.CORNER.value == "corner"


class TestDomainErrorHierarchy:
    def test_all_subclasses_of_domain_error(self):
        for exc_type in (UnsupportedConfigError, RepositoryError, LLMError):
            assert issubclass(exc_type, DomainError)

    def test_catchable_as_domain_error(self):
        with pytest.raises(DomainError):
            raise RepositoryError("boom")
