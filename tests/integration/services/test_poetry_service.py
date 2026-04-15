"""Integration tests for the poetry generation pipeline."""
from __future__ import annotations

import pytest

from src.domain.errors import UnsupportedConfigError
from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    MeterSpec,
    PoemStructure,
    RhymeScheme,
    ValidationRequest,
    ValidationResult,
)
from src.infrastructure.llm.mock import MockLLMProvider
from src.services.poetry_service import PoetryService


@pytest.mark.integration
class TestPoetryServiceGenerate:
    def test_generate_returns_result(
        self, poetry_service: PoetryService, iamb_4ft_abab: GenerationRequest,
    ):
        result = poetry_service.generate(iamb_4ft_abab)
        assert isinstance(result, GenerationResult)
        assert isinstance(result.poem, str)
        assert len(result.poem) > 0
        assert isinstance(result.validation, ValidationResult)

    def test_generate_with_different_meters(self, poetry_service: PoetryService):
        for meter_name in ["ямб", "хорей", "дактиль", "амфібрахій", "анапест"]:
            request = GenerationRequest(
                theme="природа",
                meter=MeterSpec(name=meter_name, foot_count=3),
                rhyme=RhymeScheme(pattern="ABAB"),
                structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
                max_iterations=1,
            )
            assert isinstance(poetry_service.generate(request), GenerationResult)

    def test_generate_with_different_schemes(self, poetry_service: PoetryService):
        for scheme in ["AABB", "ABAB", "ABBA", "AAAA"]:
            request = GenerationRequest(
                theme="кохання",
                meter=MeterSpec(name="ямб", foot_count=4),
                rhyme=RhymeScheme(pattern=scheme),
                structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
                max_iterations=1,
            )
            assert isinstance(poetry_service.generate(request).validation, ValidationResult)

    def test_max_iterations_respected(self, poetry_service: PoetryService):
        request = GenerationRequest(
            theme="тема",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
            structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
            max_iterations=2,
        )
        result = poetry_service.generate(request)
        assert result.validation.iterations <= 2

    def test_llm_name_property_exposed(self, poetry_service: PoetryService, mock_llm: MockLLMProvider):
        # Services expose llm_name so handlers never need to touch private attrs.
        assert poetry_service.llm_name == "MockLLMProvider"


@pytest.mark.integration
class TestPoetryServiceValidate:
    def test_validate_returns_validation_result(
        self, poetry_service: PoetryService, iamb_4ft_abab: GenerationRequest,
    ):
        poem = (
            "Весна прийшла у ліс зелений,\n"
            "Де тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\n"
            "І серце в тиші гомонить.\n"
        )
        request = ValidationRequest(
            poem_text=poem,
            meter=iamb_4ft_abab.meter,
            rhyme=iamb_4ft_abab.rhyme,
        )
        result = poetry_service.validate(request)
        assert isinstance(result, ValidationResult)
        assert 0.0 <= result.meter.accuracy <= 1.0
        assert 0.0 <= result.rhyme.accuracy <= 1.0

    def test_empty_poem_fails_validation(self, poetry_service: PoetryService):
        with pytest.raises(UnsupportedConfigError, match="poem_text must be a non-empty string"):
            ValidationRequest(
                poem_text="",
                meter=MeterSpec(name="ямб", foot_count=4),
                rhyme=RhymeScheme(pattern="ABAB"),
            )
