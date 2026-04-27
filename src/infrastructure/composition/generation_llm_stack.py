"""LLM stack composition — provider factory + reliability decorators.

Split out from ``generation.py`` so the construction order of the
decorator stack (extract → sanitize → timeout → retry → log) is the only
thing this module is responsible for.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import LLMReliabilityConfig
from src.domain.ports import (
    ILLMCallRecorder,
    ILLMProvider,
    ILLMProviderFactory,
    IPoemExtractor,
    IPoemOutputSanitizer,
    IProviderInfo,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.llm import DefaultLLMProviderFactory
from src.infrastructure.llm.decorators import (
    ExponentialBackoffRetry,
    ExtractingLLMProvider,
    LoggingLLMProvider,
    RetryingLLMProvider,
    SanitizingLLMProvider,
    TimeoutLLMProvider,
)
from src.infrastructure.llm.provider_info import LLMProviderInfo
from src.infrastructure.sanitization import (
    RegexPoemOutputSanitizer,
    SentinelPoemExtractor,
)
from src.infrastructure.tracing import InMemoryLLMCallRecorder

if TYPE_CHECKING:
    from src.composition_root import Container
    from src.domain.ports import IRegenerationPromptBuilder


class LLMStackSubContainer:
    """LLM factory, decorator stack, recorder, provider info."""

    def __init__(
        self,
        parent: Container,
        regeneration_prompt_builder_factory: object,
    ) -> None:
        # The reliability stack needs the regeneration prompt builder
        # at LLM construction time. We accept it as a callable factory
        # rather than a port instance so cycles between sibling
        # sub-containers stay impossible.
        self._parent = parent
        self._regeneration_prompt_builder_factory = regeneration_prompt_builder_factory

    def llm_factory(self) -> ILLMProviderFactory:
        return self._parent._get(
            CacheKey.LLM_FACTORY,
            lambda: DefaultLLMProviderFactory(config=self._parent.config),
        )

    def poem_output_sanitizer(self) -> IPoemOutputSanitizer:
        return self._parent._get(
            CacheKey.POEM_OUTPUT_SANITIZER, RegexPoemOutputSanitizer,
        )

    def poem_extractor(self) -> IPoemExtractor:
        return self._parent._get(CacheKey.POEM_EXTRACTOR, SentinelPoemExtractor)

    def llm_call_recorder(self) -> ILLMCallRecorder:
        return self._parent._get(CacheKey.LLM_CALL_RECORDER, InMemoryLLMCallRecorder)

    def llm(self) -> ILLMProvider:
        def factory() -> ILLMProvider:
            if self._parent.injected_llm is not None:
                # Test/CI mocks do not get wrapped; they never fail or hang.
                return self._parent.injected_llm
            regen_builder: IRegenerationPromptBuilder = (
                self._regeneration_prompt_builder_factory()  # type: ignore[operator]
            )
            raw = self.llm_factory().create(
                regen_builder,
                self.llm_call_recorder(),
            )
            return self._wrap_with_reliability(raw)

        return self._parent._get(CacheKey.LLM, factory)

    def _wrap_with_reliability(self, provider: ILLMProvider) -> ILLMProvider:
        rel: LLMReliabilityConfig = self._parent.config.llm_reliability
        recorder = self.llm_call_recorder()
        extracted = ExtractingLLMProvider(
            inner=provider,
            extractor=self.poem_extractor(),
            recorder=recorder,
        )
        sanitized = SanitizingLLMProvider(
            inner=extracted,
            sanitizer=self.poem_output_sanitizer(),
            recorder=recorder,
        )
        timed = TimeoutLLMProvider(
            inner=sanitized,
            timeout_sec=rel.timeout_sec,
        )
        retrying = RetryingLLMProvider(
            inner=timed,
            policy=ExponentialBackoffRetry(
                max_attempts=rel.retry_max_attempts,
                base_delay_sec=rel.retry_base_delay_sec,
                max_delay_sec=rel.retry_max_delay_sec,
                multiplier=rel.retry_multiplier,
            ),
            logger=self._parent.logger,
        )
        return LoggingLLMProvider(inner=retrying, logger=self._parent.logger)

    def provider_info(self) -> IProviderInfo:
        return self._parent._get(
            CacheKey.PROVIDER_INFO,
            lambda: LLMProviderInfo(self.llm()),
        )
