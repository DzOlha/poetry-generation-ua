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
- The `LLMStackSubContainer` (one of the focused sub-containers under `src/infrastructure/composition/`, composed by the `GenerationSubContainer` façade) assembles the stack in one place.
- The full decorator stack is contract-tested in `tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py`: each individual decorator (`LoggingLLMProvider`, `RetryingLLMProvider`, `TimeoutLLMProvider`, `SanitizingLLMProvider`, `ExtractingLLMProvider`) and the fully assembled stack inherit from `ILLMProviderContract`, so callers cannot tell whether they are talking to a raw provider or any combination of decorators. A refactor that breaks substitutability fails at the unit-test level.
