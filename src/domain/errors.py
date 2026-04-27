"""Domain-level exception hierarchy.

Every error the system raises intentionally should be a subclass of DomainError.
Infrastructure adapters must translate third-party exceptions into these types
so service/handler layers catch only DomainError and never bare Exception.

Each subclass advertises its own ``http_status_code`` so the HTTP error
mapper can dispatch polymorphically instead of via an ``isinstance`` chain
that has to grow every time a new domain error is added. The class name
becomes the public ``http_error_type`` automatically; subclasses override
the status code only when they need a value other than 500.
"""
from __future__ import annotations


class DomainError(Exception):
    """Root of the poetry-system exception hierarchy.

    HTTP-mapping defaults: ``http_status_code = 500`` (any unexpected
    domain fault), ``http_error_type = "DomainError"`` (the class name).
    Subclasses override only ``http_status_code``.
    """

    http_status_code: int = 500

    @property
    def http_error_type(self) -> str:
        """Stable string identifier surfaced in the JSON error body."""
        return type(self).__name__


class ConfigurationError(DomainError):
    """Raised when AppConfig or ValidationConfig is invalid or incomplete."""

    http_status_code = 400


class UnsupportedConfigError(DomainError):
    """Raised when a caller passes a meter/scheme/pattern the system cannot handle."""

    http_status_code = 422


class ValidationError(DomainError):
    """Raised when a poem/line fails validation in a way callers must handle."""

    http_status_code = 422


class RepositoryError(DomainError):
    """Raised by IThemeRepository / IMetricRepository implementations on I/O failure."""

    http_status_code = 503


class LLMError(DomainError):
    """Raised by ILLMProvider implementations when the model cannot produce text."""

    http_status_code = 502


class LLMQuotaExceededError(LLMError):
    """Raised when the LLM provider rejects the call due to a quota / rate cap.

    Distinct from generic ``LLMError`` so the HTTP layer can return 429
    (rather than 502) and the retry decorator can short-circuit — once a
    daily quota is exhausted, retrying within the same window only adds
    latency.
    """

    http_status_code = 429


class EmbedderError(DomainError):
    """Raised by IEmbedder implementations when encoding fails."""

    http_status_code = 503


class StressDictionaryError(DomainError):
    """Raised by IStressDictionary implementations when the backend is unavailable."""

    http_status_code = 503
