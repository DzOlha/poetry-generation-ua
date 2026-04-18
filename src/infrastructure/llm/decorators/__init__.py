"""LLM decorator adapters — reliability, observability, and testability.

Decorators wrap any `ILLMProvider` without modifying it. Composition order
(outermost first):

    LoggingLLMProvider              — structured INFO/ERROR per call
      └─ RetryingLLMProvider        — retries transient LLMError failures
          └─ TimeoutLLMProvider     — hard deadline per call
              └─ SanitizingLLMProvider    — line-level garbage filter
                  └─ ExtractingLLMProvider — pulls poem out of <POEM> tags
                      └─ real provider     — Gemini / Mock / future OpenAI

Extraction runs closest to the real provider so sentinel-wrapped CoT is
peeled off first; the sanitizer then handles whatever leaked through (or
the whole response if the model skipped the tags). Retry, timeout, and
logging all observe the already-cleaned text.
"""
from src.infrastructure.llm.decorators.extracting_provider import ExtractingLLMProvider
from src.infrastructure.llm.decorators.logging_provider import LoggingLLMProvider
from src.infrastructure.llm.decorators.retry_policy import ExponentialBackoffRetry
from src.infrastructure.llm.decorators.retrying_provider import RetryingLLMProvider
from src.infrastructure.llm.decorators.sanitizing_provider import SanitizingLLMProvider
from src.infrastructure.llm.decorators.timeout_provider import TimeoutLLMProvider

__all__ = [
    "ExponentialBackoffRetry",
    "ExtractingLLMProvider",
    "LoggingLLMProvider",
    "RetryingLLMProvider",
    "SanitizingLLMProvider",
    "TimeoutLLMProvider",
]
