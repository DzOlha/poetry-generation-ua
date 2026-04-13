"""HTTP error mapping ports (domain-level, framework-agnostic)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpErrorResponse:
    """Framework-agnostic representation of an HTTP error response."""

    status_code: int
    payload: dict[str, Any]


class IHttpErrorMapper(ABC):
    """Maps a `DomainError` into an `HttpErrorResponse`."""

    @abstractmethod
    def map(self, exc: Exception) -> HttpErrorResponse: ...
