"""Poetry service — thin use-case facade over IPoemGenerationPipeline + IPoemValidator.

Every dependency is injected through the constructor — the composition
root is responsible for wiring concrete implementations. Previous revisions
kept a direct `ILLMProvider` reference just to expose `.llm_name` for
telemetry; that duplicated wiring (the pipeline already holds the LLM) so
provider metadata now arrives via the narrower `IProviderInfo` port.
"""
from __future__ import annotations

from src.domain.models import (
    GenerationRequest,
    GenerationResult,
    ValidationRequest,
    ValidationResult,
)
from src.domain.ports import (
    ILogger,
    IPoemGenerationPipeline,
    IPoemValidator,
    IProviderInfo,
)


class PoetryService:
    """Use-case façade for handlers and runners."""

    def __init__(
        self,
        generation_pipeline: IPoemGenerationPipeline,
        poem_validator: IPoemValidator,
        provider_info: IProviderInfo,
        logger: ILogger,
    ) -> None:
        self._pipeline = generation_pipeline
        self._validator = poem_validator
        self._provider_info = provider_info
        self._logger: ILogger = logger

    @property
    def llm_name(self) -> str:
        """Public accessor for the configured LLM class name."""
        return self._provider_info.name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a Ukrainian poem satisfying the constraints in request."""
        return self._pipeline.build(request)

    def validate(self, request: ValidationRequest) -> ValidationResult:
        """Validate an existing poem without generation."""
        return self._validator.validate(request)
