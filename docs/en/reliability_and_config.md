# Reliability and configuration

> Every runtime knob: environment variables, LLM parameters, tuning for reasoning models, common problems and how to resolve them.

## Where things are configured

Everything runtime is the frozen dataclass [`AppConfig`](../../src/config.py), loaded from env via [`AppConfig.from_env()`](../../src/config.py). Validation happens in `__post_init__` — malformed values fail at startup, not mid-pipeline.

## Environment variables

### LLM provider

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `""` (auto) | `gemini` / `mock`. Empty = auto: Gemini if API key present, else Mock. |
| `GEMINI_API_KEY` | `""` | Gemini key. Without it the system falls back to Mock. |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | Model name (default — best quality for Ukrainian poetry; **paid**, ~\$2/1M in, ~\$12/1M out). Alternatives: `gemini-2.5-pro` (slightly cheaper, slightly worse), `gemini-2.5-flash` (free tier, but noticeably worse quality for poetry). Billing setup: see [README § Try it in 60 seconds](../../README.md#option-a--full-system-with-real-gemini-recommended). |
| `GEMINI_TEMPERATURE` | `0.9` | `[0, 2]`. Drop to `0.3` for reasoning to reduce CoT leakage into output. |
| `GEMINI_MAX_TOKENS` | `8192` | Must be ≥ 8192 for reasoning models — otherwise CoT eats the budget and the `<POEM>` envelope never gets emitted. |
| `GEMINI_DISABLE_THINKING` | `false` | Enable **only** for models that support `ThinkingConfig(thinking_budget=0)` (Gemini 2.5). Pro-preview returns HTTP 400 INVALID_ARGUMENT. |

### LLM reliability stack

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_TIMEOUT_SEC` | `120` | Hard deadline per single call. 120 s accommodates the upper end of legitimate CoT on the default `gemini-3.1-pro-preview`. If you switch to `gemini-2.5-flash` drop to `20`. |
| `LLM_RETRY_MAX_ATTEMPTS` | `2` | Attempt count, including the first try. `1` disables retries. Retrying a timeout is often futile (the model will be equally slow again), but it does cover transient 5xx / rate-limit responses. |

The full field list is in [`LLMReliabilityConfig`](../../src/config.py): `timeout_sec`, `retry_max_attempts`, `retry_base_delay_sec` (default `1.0` s), `retry_max_delay_sec` (default `10.0` s), `retry_multiplier` (default `2.0`). The backoff fields are not exposed as env vars because their practical value is low; override them in code by constructing a custom `LLMReliabilityConfig` if you need a different retry shape.

### Data / corpora

| Variable | Default | Purpose |
|----------|---------|---------|
| `CORPUS_PATH` | `corpus/uk_theme_reference_corpus.json` | Theme corpus for RAG (semantic retrieval). |
| `METRIC_EXAMPLES_PATH` | `corpus/uk_metric-rhyme_reference_corpus.json` | Metric examples. |
| `LABSE_MODEL` | `sentence-transformers/LaBSE` | HuggingFace ID of the embedding model. |
| `OFFLINE_EMBEDDER` | `false` | `true` uses a deterministic hash-based embedder (no network) for tests / CI. |

### Server

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOST` | `127.0.0.1` | FastAPI bind address. |
| `PORT` | `8000` | Port. |
| `DEBUG` | `false` | FastAPI debug mode. |

## Defensive parsing of `.env`

[`AppConfig.from_env`](../../src/config.py) uses the helper `_str(name, default)` which:

- **Strips whitespace** on both sides.
- **Strips an inline comment** (`"gemini    # provider"` → `"gemini"`). Protection against a common docker-compose artefact: the plain `env_file` parser **does not** strip `# comment` after a value, so a malformed line in `.env` would be read together with its comment.

Rule of thumb: **don't write inline comments** in `.env`. All explanations on a separate line before the variable. Example:

```env
# Empty value = auto (gemini if API key set, else mock).
LLM_PROVIDER=
```

## Behaviour under reasoning models

Gemini 2.5+ / 3.x Pro **always** emits chain-of-thought. This affects everything:

1. **`GEMINI_MAX_TOKENS` must be ≥ 8192.** 4096 is not enough — CoT hits the ceiling before the model reaches `<POEM>`. Result: the sanitizer extracts "fragments" from reasoning and the poem comes out as 1-3 lines.
2. **`LLM_TIMEOUT_SEC` = 120–180.** 60 s is a flash-model default; Pro variants sometimes think up to 2 minutes.
3. **`GEMINI_DISABLE_THINKING=true` DOES NOT WORK for Gemini 3.x Pro preview.** The model returns HTTP 400 `"This model only works in thinking mode"`. Leave `false`.
4. **Temperature 0.3** (instead of the default 0.9) reduces "exploration" and CoT leakage, but hurts variety. A trade-off.

## UI reaction to slow calls

The two slow-form pages (`/generate`, `/evaluate`) have client-side protection:

- **Spinner + elapsed-time counter** on the button immediately after submit.
- **"Taking longer than expected" banner** appears after 60 s — in case the reasoning model really is thinking long.
- **"Cancel" button** aborts the `fetch()` client-side via `AbortController`. The server **continues** to process the request (sync handler + threadpool), but the user can leave. Tokens still burn, response drops on the floor.

Fast forms (`/validate`, `/detect`) have no Cancel — native submit with deferred spinner.

Full logic in [`main.js`](../../src/handlers/web/static/main.js).

## Algorithmic thresholds

Not env vars but in-code constants. Edited via `ValidationConfig` / `DetectionConfig`:

| Parameter | File | Purpose |
|-----------|------|---------|
| `RHYME_THRESHOLD` | `ValidationConfig` | Minimum similarity for a pair to count as rhyming. Default `0.5`. |
| `CLAUSULA_MAX_CONSONANT_EDITS` | `ValidationConfig` | Allowed consonant edits in the clausula. |
| `STANZA_SAMPLE_LINES` | `DetectionConfig` | How many lines to sample from a poem in brute-force detection. |
| `FEET_MIN_MAX` | `DetectionConfig` | Range for foot_count sweep. |
| `_MIN_CYR_LETTERS` / `_MIN_CYR_LETTERS_PUNCT` | `aggregates.py` | Minimum Cyrillic letters for a valid line (without/with punctuation). |

## Docker + env_file

[`docker-compose.yml`](../../docker/docker-compose.yml) uses `env_file: ../.env`. Which means:

- **Tests inside the container read host's `.env`.** A broken line there → every test fails at `AppConfig()`.
- **`.env` is gitignored.** Sync with the latest env vars manually from [.env.example](../../.env.example).
- **Inline comments in `.env`** break docker-compose env_file. The `_str()` helper in config.py rescues, but avoid it.

## HTTP error mapping

The API surface translates `DomainError` subclasses into HTTP responses through [`DefaultHttpErrorMapper`](../../src/infrastructure/http/error_mapper.py). The mapper itself is a two-line check: each `DomainError` subclass advertises its own `http_status_code` and `http_error_type` (see [`src/domain/errors.py`](../../src/domain/errors.py)), and the mapper just reads those fields. Adding a new error type does **not** require editing the mapper.

| Domain error | HTTP status | Where it comes from |
|--------------|-------------|---------------------|
| `UnsupportedConfigError` | 422 | Caller asks for a meter / scheme combination the system cannot handle |
| `ConfigurationError` | 400 | Malformed `AppConfig` / `ValidationConfig` values |
| `ValidationError` | 422 | A poem/line fails validation in a way the caller must handle |
| `RepositoryError` | 503 | `IThemeRepository` / `IMetricRepository` I/O failure |
| `EmbedderError` | 503 | `IEmbedder` encoding failure |
| `StressDictionaryError` | 503 | `IStressDictionary` backend unavailable |
| `LLMError` | 502 | Anything the decorator stack surfaces — Gemini failures, timeouts, empty-after-sanitization, retries exhausted |
| `DomainError` (root) | 500 | Unexpected domain fault |
| Anything else | 500 | Last-resort fallback (`InternalServerError`) |

The contract is exercised by `tests/unit/infrastructure/http/test_error_mapper.py`.

## Time abstraction: `IClock` and `IDelayer`

Services never read the wall clock or call `time.sleep` directly. They depend on two ports defined in [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py): `IClock.now()` for monotonic elapsed time and `IDelayer.sleep(seconds)` for cooperative throttling. The production adapters (`SystemClock` / `SystemDelayer`) wrap `time.perf_counter` / `time.sleep`; tests inject `FakeClock` / `FakeDelayer` doubles. Note that `RetryingLLMProvider` uses its own injectable `sleep_fn` parameter for the same reason — backoff timing stays observable in tests without slowing them down.

## Common problem scenarios

| Symptom | Quick diagnosis | Fix |
|---------|-----------------|-----|
| `ConfigurationError: Unknown llm_provider ...` on startup | Broken line in `.env` | Remove the inline comment from that line |
| `Gemini call failed: 400 INVALID_ARGUMENT. {'message': 'Budget 0 is invalid...'}` | Model does not support `thinking_budget=0` | `GEMINI_DISABLE_THINKING=false` |
| `LLM regenerate_lines exceeded timeout of 60.0s` | Stale flash default, reasoning model too slow | `LLM_TIMEOUT_SEC=180` |
| Iteration 0 shows only 1 line instead of 4 | CoT truncates output before `<POEM>` | `GEMINI_MAX_TOKENS=12288` or higher |
| `LLM produced no valid poem lines after sanitization` (after N retries) | Model emits only CoT, never commits | Lower `GEMINI_TEMPERATURE` to `0.3` + raise max_tokens |
| Spinner spins forever on first call | LaBSE weights loading (~1 GB) | Wait out the first call, then the cache handles it |

## See also

- [llm_decorator_stack.md](./llm_decorator_stack.md) — full reliability-decision architecture.
- [sanitization_pipeline.md](./sanitization_pipeline.md) — what to do when output stays garbage.
- [feedback_loop.md](./feedback_loop.md) — how timeout / retry interact with the feedback loop.
- [.env.example](../../.env.example) — up-to-date config template.
