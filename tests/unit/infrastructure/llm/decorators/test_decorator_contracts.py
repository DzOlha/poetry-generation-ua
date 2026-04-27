"""Contract coverage for the LLM decorator stack.

Each decorator wraps an ``ILLMProvider`` so it must itself satisfy the
``ILLMProviderContract``: callers should be unable to tell whether they're
talking to a raw provider or one wrapped in any combination of decorators.
The audit flagged the absence of these guarantees as the largest test gap
in the project — without them, a refactor of any decorator can silently
break the substitutability that the architecture relies on.
"""
from __future__ import annotations

import pytest

from src.domain.errors import LLMError
from src.domain.ports import (
    ILLMCallRecorder,
    ILLMProvider,
    ILogger,
    IPoemExtractor,
    IPoemOutputSanitizer,
    IRetryPolicy,
)
from src.infrastructure.llm.decorators import (
    ExtractingLLMProvider,
    LoggingLLMProvider,
    RetryingLLMProvider,
    SanitizingLLMProvider,
    TimeoutLLMProvider,
)
from src.infrastructure.tracing import NullLLMCallRecorder
from tests.contracts.llm_provider_contract import ILLMProviderContract

_VALID_POEM = (
    "рядок один\n"
    "рядок два\n"
    "рядок три\n"
    "рядок чотири\n"
)


# ---------------------------------------------------------------------------
# Test doubles — minimal collaborators for the decorators under test
# ---------------------------------------------------------------------------

class _PassthroughProvider(ILLMProvider):
    """Inner provider that always returns a valid poem string.

    The contract exercises the decorator's wrapping discipline; the inner
    provider is irrelevant beyond returning something non-empty for both
    operations.
    """

    def generate(self, prompt: str) -> str:
        del prompt
        return _VALID_POEM

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        del poem, feedback
        return _VALID_POEM


class _IdentityExtractor(IPoemExtractor):
    """Extractor that does nothing — keeps the decorator behaviour observable."""

    def extract(self, text: str) -> str:
        return text


class _IdentitySanitizer(IPoemOutputSanitizer):
    """Sanitizer that lets every line through unchanged."""

    def sanitize(self, text: str) -> str:
        return text


class _NeverRetryPolicy(IRetryPolicy):
    """Retry policy that surfaces failures immediately.

    The contract suite never makes the inner provider fail, so the decorator
    only sees the success path. We still inject a real policy so the
    constructor is exercised the same way it would be in production.
    """

    def should_retry(self, attempt: int, exc: Exception) -> bool:
        del attempt, exc
        return False

    def next_delay_sec(self, attempt: int) -> float:
        del attempt
        return 0.0


class _SilentLogger(ILogger):
    """No-op logger so the contract suite stays quiet."""

    def info(self, message: str, **fields: object) -> None:
        del message, fields

    def warning(self, message: str, **fields: object) -> None:
        del message, fields

    def error(self, message: str, **fields: object) -> None:
        del message, fields


def _recorder() -> ILLMCallRecorder:
    return NullLLMCallRecorder()


# ---------------------------------------------------------------------------
# Contract tests — one subclass per decorator
# ---------------------------------------------------------------------------

class TestLoggingLLMProviderContract(ILLMProviderContract):
    def _make_provider(self) -> ILLMProvider:
        return LoggingLLMProvider(
            inner=_PassthroughProvider(),
            logger=_SilentLogger(),
        )


class TestRetryingLLMProviderContract(ILLMProviderContract):
    def _make_provider(self) -> ILLMProvider:
        return RetryingLLMProvider(
            inner=_PassthroughProvider(),
            policy=_NeverRetryPolicy(),
            logger=_SilentLogger(),
            sleep_fn=lambda _seconds: None,
        )


class TestTimeoutLLMProviderContract(ILLMProviderContract):
    def _make_provider(self) -> ILLMProvider:
        return TimeoutLLMProvider(
            inner=_PassthroughProvider(),
            timeout_sec=5.0,
        )


class TestSanitizingLLMProviderContract(ILLMProviderContract):
    def _make_provider(self) -> ILLMProvider:
        return SanitizingLLMProvider(
            inner=_PassthroughProvider(),
            sanitizer=_IdentitySanitizer(),
            recorder=_recorder(),
        )


class TestExtractingLLMProviderContract(ILLMProviderContract):
    def _make_provider(self) -> ILLMProvider:
        return ExtractingLLMProvider(
            inner=_PassthroughProvider(),
            extractor=_IdentityExtractor(),
            recorder=_recorder(),
        )


class TestFullDecoratorStackContract(ILLMProviderContract):
    """Full production-shaped stack: logging > retry > timeout > sanitize > extract."""

    def _make_provider(self) -> ILLMProvider:
        inner: ILLMProvider = ExtractingLLMProvider(
            inner=_PassthroughProvider(),
            extractor=_IdentityExtractor(),
            recorder=_recorder(),
        )
        inner = SanitizingLLMProvider(
            inner=inner,
            sanitizer=_IdentitySanitizer(),
            recorder=_recorder(),
        )
        inner = TimeoutLLMProvider(inner=inner, timeout_sec=5.0)
        inner = RetryingLLMProvider(
            inner=inner,
            policy=_NeverRetryPolicy(),
            logger=_SilentLogger(),
            sleep_fn=lambda _seconds: None,
        )
        return LoggingLLMProvider(inner=inner, logger=_SilentLogger())


# ---------------------------------------------------------------------------
# A complementary check: when the inner provider raises a LLMError, every
# wrapping decorator must propagate it as LLMError so callers can rely on the
# contract regardless of how deep in the stack the failure originated.
# ---------------------------------------------------------------------------

class _AlwaysFailingProvider(ILLMProvider):
    def generate(self, prompt: str) -> str:
        del prompt
        raise LLMError("inner failure")

    def regenerate_lines(self, poem: str, feedback: list[str]) -> str:
        del poem, feedback
        raise LLMError("inner failure")


def _build_failing_stack() -> ILLMProvider:
    inner: ILLMProvider = ExtractingLLMProvider(
        inner=_AlwaysFailingProvider(),
        extractor=_IdentityExtractor(),
        recorder=_recorder(),
    )
    inner = SanitizingLLMProvider(
        inner=inner,
        sanitizer=_IdentitySanitizer(),
        recorder=_recorder(),
    )
    inner = TimeoutLLMProvider(inner=inner, timeout_sec=5.0)
    inner = RetryingLLMProvider(
        inner=inner,
        policy=_NeverRetryPolicy(),
        logger=_SilentLogger(),
        sleep_fn=lambda _seconds: None,
    )
    return LoggingLLMProvider(inner=inner, logger=_SilentLogger())


class TestFullStackPropagatesLLMError:
    def test_generate_propagates_llm_error(self) -> None:
        provider = _build_failing_stack()
        with pytest.raises(LLMError):
            provider.generate("anything")

    def test_regenerate_propagates_llm_error(self) -> None:
        provider = _build_failing_stack()
        with pytest.raises(LLMError):
            provider.regenerate_lines("poem", ["fix"])
