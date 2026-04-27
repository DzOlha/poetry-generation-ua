"""Unit tests for `DefaultHttpErrorMapper`.

Every branch of the DomainError hierarchy must map to its documented
HTTP status code. The mapping is the public contract handlers rely on —
changing it is a breaking change and these tests enforce that.
"""
from __future__ import annotations

import pytest

from src.domain.errors import (
    ConfigurationError,
    DomainError,
    EmbedderError,
    LLMError,
    LLMQuotaExceededError,
    RepositoryError,
    StressDictionaryError,
    UnsupportedConfigError,
    ValidationError,
)
from src.domain.ports import HttpErrorResponse
from src.infrastructure.http.error_mapper import DefaultHttpErrorMapper


@pytest.fixture
def mapper() -> DefaultHttpErrorMapper:
    return DefaultHttpErrorMapper()


class TestDefaultHttpErrorMapperStatusCodes:
    """Verify each domain exception maps to its contracted status code."""

    @pytest.mark.parametrize(
        "exc,expected_status,expected_type",
        [
            (UnsupportedConfigError("bad meter"), 422, "UnsupportedConfigError"),
            (ValidationError("poem invalid"), 422, "ValidationError"),
            (ConfigurationError("bad cfg"), 400, "ConfigurationError"),
            (LLMError("upstream down"), 502, "LLMError"),
            (
                LLMQuotaExceededError("limit reached"),
                429,
                "LLMQuotaExceededError",
            ),
            (EmbedderError("no model"), 503, "EmbedderError"),
            (RepositoryError("no corpus"), 503, "RepositoryError"),
            (StressDictionaryError("no dict"), 503, "StressDictionaryError"),
            (DomainError("generic domain"), 500, "DomainError"),
        ],
    )
    def test_domain_errors_map_to_expected_status(
        self,
        mapper: DefaultHttpErrorMapper,
        exc: Exception,
        expected_status: int,
        expected_type: str,
    ) -> None:
        response = mapper.map(exc)
        assert isinstance(response, HttpErrorResponse)
        assert response.status_code == expected_status
        assert response.payload["type"] == expected_type
        assert response.payload["error"] == str(exc)

    def test_non_domain_exception_is_internal_server_error(
        self, mapper: DefaultHttpErrorMapper,
    ) -> None:
        response = mapper.map(RuntimeError("unexpected"))
        assert response.status_code == 500
        assert response.payload["type"] == "InternalServerError"

    def test_empty_message_falls_back_to_exception_name(
        self, mapper: DefaultHttpErrorMapper,
    ) -> None:
        response = mapper.map(ValidationError(""))
        # Empty str(exc) is falsy — mapper should surface the class name.
        assert response.payload["error"] == "ValidationError"


class TestSubclassPriority:
    """More specific subclasses must win over their parent DomainError branch."""

    def test_unsupported_config_is_422_not_500(
        self, mapper: DefaultHttpErrorMapper,
    ) -> None:
        # UnsupportedConfigError inherits from DomainError; must not fall
        # through to the generic 500 branch.
        assert mapper.map(UnsupportedConfigError("x")).status_code == 422

    def test_llm_error_is_502_not_500(self, mapper: DefaultHttpErrorMapper) -> None:
        assert mapper.map(LLMError("x")).status_code == 502
