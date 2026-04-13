"""Domain-level exception hierarchy.

Every error the system raises intentionally should be a subclass of DomainError.
Infrastructure adapters must translate third-party exceptions into these types
so service/handler layers catch only DomainError and never bare Exception.
"""
from __future__ import annotations


class DomainError(Exception):
    """Root of the poetry-system exception hierarchy."""


class ConfigurationError(DomainError):
    """Raised when AppConfig or ValidationConfig is invalid or incomplete."""


class UnsupportedConfigError(DomainError):
    """Raised when a caller passes a meter/scheme/pattern the system cannot handle."""


class ValidationError(DomainError):
    """Raised when a poem/line fails validation in a way callers must handle."""


class RepositoryError(DomainError):
    """Raised by IThemeRepository / IMetricRepository implementations on I/O failure."""


class LLMError(DomainError):
    """Raised by ILLMProvider implementations when the model cannot produce text."""


class EmbedderError(DomainError):
    """Raised by IEmbedder implementations when encoding fails."""


class StressDictionaryError(DomainError):
    """Raised by IStressDictionary implementations when the backend is unavailable."""
