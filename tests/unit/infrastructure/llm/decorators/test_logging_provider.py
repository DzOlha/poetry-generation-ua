"""Tests for `LoggingLLMProvider`."""
from __future__ import annotations

import pytest

from src.domain.errors import LLMError
from src.domain.ports import ILLMProvider
from src.infrastructure.llm.decorators import LoggingLLMProvider
from tests.fixtures.infrastructure import RecordingLogger


class _OkProvider(ILLMProvider):
    def generate(self, prompt: str) -> str:
        return "poem"

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        return "refined"


class _FailingProvider(ILLMProvider):
    def generate(self, prompt: str) -> str:
        raise LLMError("boom")

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        raise LLMError("boom")


class TestLoggingLLMProvider:
    def test_success_emits_info(self) -> None:
        logger = RecordingLogger()
        provider = LoggingLLMProvider(inner=_OkProvider(), logger=logger)
        assert provider.generate("hello") == "poem"
        assert len(logger.infos) == 1
        assert logger.infos[0][0] == "LLM call ok"
        assert logger.errors == []

    def test_failure_emits_error_and_reraises(self) -> None:
        logger = RecordingLogger()
        provider = LoggingLLMProvider(inner=_FailingProvider(), logger=logger)
        with pytest.raises(LLMError):
            provider.generate("hello")
        assert len(logger.errors) == 1
        assert logger.errors[0][0] == "LLM call failed"
        assert logger.infos == []
