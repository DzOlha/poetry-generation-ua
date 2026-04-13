# ADR-003: Contract Tests for Port Implementations

## Status
Accepted

## Context
Several domain ports have multiple implementations (e.g., `IEmbedder` has `LaBSEEmbedder`, `OfflineDeterministicEmbedder`, `CompositeEmbedder`; `ILLMProvider` has `GeminiProvider`, `MockLLMProvider`; `IThemeRepository` has 3 adapters). Each must satisfy the same behavioral contract.

## Decision
Define abstract contract test base classes in `tests/contracts/`:
- `IEmbedderContract` — encode returns non-empty vector, deterministic, stable dimension
- `ILLMProviderContract` — generate/regenerate return non-empty strings, empty feedback accepted
- `IMetricCalculatorContract` — non-empty name, finite float result, no context mutation

Concrete test classes inherit from the contract and provide the implementation via `_make_*()`.

## Consequences
- Adding a new port implementation requires only a new concrete test class that inherits from the contract.
- Contract violations are caught at the unit test level, not at integration time.
- Liskov Substitution Principle is enforced via tests, not just code review.
