"""Pure unit tests for `PoetryService` — fakes all ports, no pipeline.

These tests complement the integration-level
`tests/integration/services/test_poetry_service.py` which runs the full
pipeline. Here we verify that the service is genuinely a thin façade:
every public method forwards to the injected port and does not add its
own business logic.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    MeterResult,
    MeterSpec,
    PoemStructure,
    RhymeResult,
    RhymeScheme,
    ValidationRequest,
    ValidationResult,
)
from src.domain.ports import (
    ILLMProvider,
    ILogger,
    IPoemGenerationPipeline,
    IPoemValidator,
)
from src.infrastructure.llm.provider_info import LLMProviderInfo
from src.services.poetry_service import PoetryService

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

@dataclass
class FakeGenerationPipeline(IPoemGenerationPipeline):
    canned: GenerationResult
    calls: list[GenerationRequest]

    def build(self, request: GenerationRequest) -> GenerationResult:
        self.calls.append(request)
        return self.canned


@dataclass
class FakePoemValidator(IPoemValidator):
    canned: ValidationResult
    calls: list[tuple[ValidationRequest, int]]

    def validate(
        self, request: ValidationRequest, iterations: int = 0,
    ) -> ValidationResult:
        self.calls.append((request, iterations))
        return self.canned


class FakeLLM(ILLMProvider):
    def generate(self, prompt: str) -> str:
        return ""

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return ""


class NullLogger(ILogger):
    def info(self, message: str, **fields) -> None: ...
    def warning(self, message: str, **fields) -> None: ...
    def error(self, message: str, **fields) -> None: ...


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _make_request() -> GenerationRequest:
    return GenerationRequest(
        theme="весна",
        meter=MeterSpec(name="ямб", foot_count=4),
        rhyme=RhymeScheme(pattern="ABAB"),
        structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
    )


def _make_validation_result(is_valid: bool = True) -> ValidationResult:
    return ValidationResult(
        meter=MeterResult(ok=is_valid, accuracy=1.0 if is_valid else 0.3),
        rhyme=RhymeResult(ok=is_valid, accuracy=1.0 if is_valid else 0.4),
    )


@pytest.fixture
def service_and_fakes():
    pipeline = FakeGenerationPipeline(
        canned=GenerationResult(
            poem="рядок один\nрядок два\nрядок три\nрядок чотири\n",
            validation=_make_validation_result(True),
        ),
        calls=[],
    )
    validator = FakePoemValidator(canned=_make_validation_result(True), calls=[])
    fake_llm = FakeLLM()
    service = PoetryService(
        generation_pipeline=pipeline,
        poem_validator=validator,
        provider_info=LLMProviderInfo(fake_llm),
        logger=NullLogger(),
    )
    return service, pipeline, validator, fake_llm


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_delegates_to_pipeline(self, service_and_fakes) -> None:
        service, pipeline, _, _ = service_and_fakes
        req = _make_request()
        result = service.generate(req)
        assert result is pipeline.canned
        assert pipeline.calls == [req]

    def test_does_not_touch_validator(self, service_and_fakes) -> None:
        service, _, validator, _ = service_and_fakes
        service.generate(_make_request())
        assert validator.calls == []  # generate() must not run standalone validation

    def test_returns_exact_pipeline_result(self, service_and_fakes) -> None:
        service, pipeline, _, _ = service_and_fakes
        result = service.generate(_make_request())
        assert result.poem == pipeline.canned.poem
        assert result.validation.is_valid is True


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestValidate:
    def test_delegates_to_validator(self, service_and_fakes) -> None:
        service, _, validator, _ = service_and_fakes
        req = ValidationRequest(
            poem_text="рядок",
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        )
        result = service.validate(req)
        assert result is validator.canned
        assert validator.calls == [(req, 0)]

    def test_does_not_touch_pipeline(self, service_and_fakes) -> None:
        service, pipeline, _, _ = service_and_fakes
        service.validate(
            ValidationRequest(
                poem_text="x",
                meter=MeterSpec(name="ямб", foot_count=4),
                rhyme=RhymeScheme(pattern="ABAB"),
            )
        )
        assert pipeline.calls == []  # validate() must not run generation


# ---------------------------------------------------------------------------
# llm_name accessor (delegates to IProviderInfo)
# ---------------------------------------------------------------------------

class TestLLMAccessors:
    def test_llm_name_is_class_name(self, service_and_fakes) -> None:
        service, _, _, _ = service_and_fakes
        assert service.llm_name == "FakeLLM"
