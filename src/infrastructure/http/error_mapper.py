"""Default `IHttpErrorMapper` — dispatches polymorphically on DomainError.

After the audit, each ``DomainError`` subclass owns its own
``http_status_code`` and ``http_error_type``. The mapper is reduced to a
two-line check: domain errors carry their own metadata; anything else
falls through to the standard 500 response. Adding a new domain error
type no longer requires editing this module — the OCP-friendly approach
the audit recommended.

Mapping policy (stable contract, exercised in
``tests/unit/infrastructure/http/test_error_mapper.py``):

    UnsupportedConfigError → 422
    ConfigurationError     → 400
    ValidationError        → 422
    RepositoryError        → 503
    EmbedderError          → 503
    StressDictionaryError  → 503
    LLMQuotaExceededError  → 429
    LLMError               → 502
    DomainError (root)     → 500
    Exception              → 500  (last-resort fallback)
"""
from __future__ import annotations

from src.domain.errors import DomainError
from src.domain.ports import HttpErrorResponse, IHttpErrorMapper


class DefaultHttpErrorMapper(IHttpErrorMapper):
    """Maps DomainError subclasses to framework-agnostic `HttpErrorResponse`."""

    def map(self, exc: Exception) -> HttpErrorResponse:
        if isinstance(exc, DomainError):
            return HttpErrorResponse(
                status_code=exc.http_status_code,
                payload={
                    "error": str(exc) or exc.__class__.__name__,
                    "type": exc.http_error_type,
                },
            )
        return HttpErrorResponse(
            status_code=500,
            payload={
                "error": str(exc) or exc.__class__.__name__,
                "type": "InternalServerError",
            },
        )
