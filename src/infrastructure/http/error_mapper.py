"""Default `IHttpErrorMapper` — maps DomainError subclasses to HTTP responses.

This adapter lives in the infrastructure layer because it knows the full
domain-error taxonomy; handlers import it via `IHttpErrorMapper` only,
keeping FastAPI-specific translation at the outermost edge of the system.

Mapping policy (stable contract, tested in
`tests/unit/infrastructure/http/test_error_mapper.py`):

    UnsupportedConfigError → 422  (caller asked for something the system
                                   cannot handle — degenerate meter/scheme)
    ConfigurationError     → 400  (caller-facing config problem)
    ValidationError        → 422  (poem failed structural validation)
    RepositoryError        → 503  (corpus/embedding source unavailable)
    EmbedderError          → 503  (embedding backend unavailable)
    StressDictionaryError  → 503  (linguistic backend unavailable)
    LLMError               → 502  (upstream LLM refused / crashed)
    DomainError (root)     → 500  (any unexpected domain fault)
    Exception              → 500  (anything else — last-resort fallback)
"""
from __future__ import annotations

from src.domain.errors import (
    ConfigurationError,
    DomainError,
    EmbedderError,
    LLMError,
    RepositoryError,
    StressDictionaryError,
    UnsupportedConfigError,
    ValidationError,
)
from src.domain.ports import HttpErrorResponse, IHttpErrorMapper


class DefaultHttpErrorMapper(IHttpErrorMapper):
    """Maps DomainError subclasses to framework-agnostic `HttpErrorResponse`."""

    def map(self, exc: Exception) -> HttpErrorResponse:
        status, error_type = self._classify(exc)
        return HttpErrorResponse(
            status_code=status,
            payload={
                "error": str(exc) or exc.__class__.__name__,
                "type": error_type,
            },
        )

    @staticmethod
    def _classify(exc: Exception) -> tuple[int, str]:
        # Most specific subclasses first — order matters because subclasses
        # would otherwise match their parent's branch.
        if isinstance(exc, UnsupportedConfigError):
            return 422, "UnsupportedConfigError"
        if isinstance(exc, ValidationError):
            return 422, "ValidationError"
        if isinstance(exc, ConfigurationError):
            return 400, "ConfigurationError"
        if isinstance(exc, LLMError):
            return 502, "LLMError"
        if isinstance(exc, EmbedderError):
            return 503, "EmbedderError"
        if isinstance(exc, RepositoryError):
            return 503, "RepositoryError"
        if isinstance(exc, StressDictionaryError):
            return 503, "StressDictionaryError"
        if isinstance(exc, DomainError):
            return 500, "DomainError"
        return 500, "InternalServerError"
