"""LLM decorator adapters — reliability, observability, and testability.

Decorators wrap any `ILLMProvider` without modifying it. Composition order
(outermost first):

    LoggingLLMProvider          — structured INFO/ERROR per call
      └─ RetryingLLMProvider    — retries transient LLMError failures
          └─ TimeoutLLMProvider — hard deadline per call
              └─ real provider  — Gemini / Mock / future OpenAI

The outer layers see the original call arguments; the inner layers see the
layered errors. This keeps each concern independently testable and allows
production wiring to enable or disable any tier via the composition root.
"""
from src.infrastructure.llm.decorators.logging_provider import LoggingLLMProvider
from src.infrastructure.llm.decorators.retry_policy import ExponentialBackoffRetry
from src.infrastructure.llm.decorators.retrying_provider import RetryingLLMProvider
from src.infrastructure.llm.decorators.timeout_provider import TimeoutLLMProvider

__all__ = [
    "ExponentialBackoffRetry",
    "LoggingLLMProvider",
    "RetryingLLMProvider",
    "TimeoutLLMProvider",
]
