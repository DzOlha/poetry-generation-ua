# LLM decorator stack

> Reference for the layered decorators between the pipeline and the real LLM: what each layer does, the composition order, and how errors propagate.

## Why decorators

The pipeline talks to the LLM through a single abstract port `ILLMProvider`. Every reliability concern (retry, timeout, garbage filtering, tracing) is a separate decorator that **wraps** the previous one. This gives:

- A single configuration point ([`_wrap_with_reliability`](../../src/infrastructure/composition/generation_llm_stack.py) in `LLMStackSubContainer`).
- The ability to enable / disable individual tiers without touching the pipeline.
- A natural hook for new concerns (rate-limit, circuit-breaker) — just another `ILLMProvider`.

## Layer order (outermost → innermost)

```
LoggingLLMProvider              ← INFO/ERROR log per call
  └─ RetryingLLMProvider        ← retries on LLMError
      └─ TimeoutLLMProvider     ← hard deadline
          └─ SanitizingLLMProvider   ← garbage filter, empty → LLMError
              └─ ExtractingLLMProvider ← peel <POEM>…</POEM>
                  └─ GeminiProvider / MockLLMProvider (real)
```

Top-down, each layer sees the output of the inner one. Only processed errors (`LLMError`s) leak outward — raw infrastructure exceptions are hidden.

## What each layer does

| Layer | Position rationale | Propagates as | Role |
|-------|--------------------|---------------|------|
| `LoggingLLMProvider` ([file](../../src/infrastructure/llm/decorators/logging_provider.py)) | Outermost — sees the original caller arguments and the final outcome after every inner retry/timeout. | `LLMError` (re-raised) | Structured `INFO` on success / `ERROR` on failure with `duration_sec` and `output_chars`. |
| `RetryingLLMProvider` ([file](../../src/infrastructure/llm/decorators/retrying_provider.py)) | Sits above timeout so a single overrun is one retryable attempt, not the whole budget. | `LLMError` after the final attempt | Retries on `LLMError` per the injected `IRetryPolicy` (default `ExponentialBackoffRetry`: `retry_max_attempts`, `retry_base_delay_sec`, `retry_multiplier`, `retry_max_delay_sec`). Uses an injected `sleep_fn` so tests stay synchronous. |
| `TimeoutLLMProvider` ([file](../../src/infrastructure/llm/decorators/timeout_provider.py)) | Above sanitization so the deadline is measured against the model's response, not the cleaning work. | `LLMError` | Runs the inner call on a daemon thread and `join`s with `timeout_sec`. On overrun raises `LLMError`; on unexpected (non-`LLMError`) exceptions inside the thread it wraps them as `LLMError` so retry treats them uniformly. **Does NOT cancel the underlying thread** — Python has no portable thread-kill primitive, so the request keeps running in the background until it finishes naturally; only the caller sees a deterministic failure. |
| `SanitizingLLMProvider` ([file](../../src/infrastructure/llm/decorators/sanitizing_provider.py)) | Inside timeout/retry but outside extraction so retry attempts always observe the cleaned text. | `LLMError` if every line is dropped | Runs output through `IPoemOutputSanitizer`. Records the cleaned text on `ILLMCallRecorder`. If the sanitizer returns `""` (response was pure CoT/scansion) it raises `LLMError` so the retry layer can ask for another attempt — silently returning garbage would let the bad response reach the validator. |
| `ExtractingLLMProvider` ([file](../../src/infrastructure/llm/decorators/extracting_provider.py)) | Innermost wrapper — closest to the real provider so sentinel-wrapped CoT is peeled off first. | Pass-through (no exceptions of its own) | Pulls the content between `<POEM>…</POEM>` via `IPoemExtractor`. Records `raw` and `extracted` text in `ILLMCallRecorder` for tracing. Missing/empty tags → returns input unchanged (sanitizer salvages). |
| `GeminiProvider` / `MockLLMProvider` ([gemini.py](../../src/infrastructure/llm/gemini.py), [mock.py](../../src/infrastructure/llm/mock.py)) | Real provider at the core. | `LLMError` from Gemini failures | Real Gemini HTTP call (also pushes `usage_metadata` into the recorder) or a deterministic test double. |

## Interaction: what sees what

- `LoggingLLMProvider` **does not see** inner retries — it only observes the final success / failure.
- `RetryingLLMProvider` retries only when the inner layer raises `LLMError` **and** the injected policy permits it. The default `ExponentialBackoffRetry.should_retry` deliberately short-circuits on `LLMQuotaExceededError`: once a daily quota is exhausted, retrying within the same window just adds latency before the same error (HTTP 429). Every other `LLMError` is retried, including timeout — for timeouts this is often pointless (the model takes just as long again), but the same branch covers transient model failures (5xx, rate-limit) where retrying does help.
- `SanitizingLLMProvider` can raise `LLMError` on empty output — the one case where retry gets a chance to fix "model produced CoT only".
- `ExtractingLLMProvider` **always** writes to `ILLMCallRecorder` even on inner failure. Full trace for UI / debug.

## Behavioural guarantees / Contract tests

The stack is covered by [`tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py`](../../tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py). Each decorator individually — and the full production stack assembled top-to-bottom — runs against `ILLMProviderContract`, which exercises both `generate` and `regenerate_lines`. The same suite includes `TestFullStackPropagatesLLMError`: when the innermost provider raises `LLMError`, every wrapping decorator must propagate it as `LLMError`. This nails down the substitutability the architecture relies on:

- The decorator wrapping discipline cannot be silently broken — if a refactor changes a return shape or an exception type, the contract suite fails before the change reaches review.
- Tests reuse `NullLLMCallRecorder` and `_NeverRetryPolicy`; they never wait on real wall-clock or real I/O.

## Gotchas

- **Timeout does not kill the thread.** `Thread.join(timeout)` only frees the caller. The actual Gemini HTTP call keeps running in the daemon thread until it completes naturally. Tokens burn. The only way to save them is an `asyncio` refactor of the pipeline.
- **Mock bypass.** If `Container.injected_llm` is set, the decorator stack is skipped entirely and the mock goes into the pipeline as-is — see the explicit branch in [`LLMStackSubContainer.llm`](../../src/infrastructure/composition/generation_llm_stack.py). The same logic also means a `MockLLMProvider` instantiated by the factory under `LLM_PROVIDER=mock` **is** still wrapped by the stack — only the test/CI `injected_llm` path is unwrapped. **Never** inject mocks in production; tests only.
- **Gemini 3.x Pro preview** does not support `ThinkingConfig(thinking_budget=0)` — returns HTTP 400. Hence `gemini_disable_thinking` defaults to `False`. See [reliability_and_config.md](./reliability_and_config.md).
- **Empty response.** `GeminiProvider` raises `LLMError` when `response.text` is empty. That bubbles straight to retry, skipping the sanitizer.

## Extending the stack

Adding a new tier = new class implementing `ILLMProvider` that holds an `inner`. Wire it into [`LLMStackSubContainer._wrap_with_reliability`](../../src/infrastructure/composition/generation_llm_stack.py) at the appropriate level (the composition root is the only place that knows the decorator order).

When you add a decorator, also add a contract subclass to [`test_decorator_contracts.py`](../../tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py) and update `TestFullDecoratorStackContract` so the new layer is exercised inside the full stack as well.

Sensible candidates:
- **RateLimitingLLMProvider** — sliding window on N calls/min so you never hit the quota.
- **CircuitBreakerLLMProvider** — after N consecutive failures, open the circuit and fail fast until the provider recovers.
- **CachingLLMProvider** — LRU cache keyed on prompt hash for deterministic outputs in tests/CI.

Every new layer **must** preserve the `ILLMProvider` contract: `generate(prompt) -> str`, `regenerate_lines(poem, feedback) -> str`. Errors **must** be `LLMError` subclasses — otherwise retry will not catch them.

## See also

- [ADR-002: LLM reliability via decorator stack](../adr/002-llm-decorator-stack.md) — short decision-record format.
- [sanitization_pipeline.md](./sanitization_pipeline.md) — what sanitizer + extractor actually do.
- [reliability_and_config.md](./reliability_and_config.md) — how to tune timeout / retry.
