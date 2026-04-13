# ADR-002: LLM Reliability via Decorator Stack

## Status
Accepted

## Context
LLM API calls are unreliable: they can timeout, return transient errors, or produce empty responses. Every caller needs consistent retry, timeout, and logging behavior.

## Decision
Wrap the raw `ILLMProvider` in a layered decorator stack:

```
LoggingLLMProvider (outermost — logs duration + errors)
  → RetryingLLMProvider (exponential backoff via IRetryPolicy)
    → TimeoutLLMProvider (thread-based timeout)
      → GeminiProvider / MockLLMProvider (real provider)
```

Each decorator implements `ILLMProvider` and wraps the next. Configuration comes from `LLMReliabilityConfig` (timeout, retry count, backoff parameters).

## Consequences
- Adding a new decorator (e.g., rate limiting, circuit breaker) requires only a new `ILLMProvider` wrapper.
- Test doubles skip the decorator stack entirely — injected mocks are used as-is.
- The `GenerationSubContainer._wrap_with_reliability()` method assembles the stack in one place.
