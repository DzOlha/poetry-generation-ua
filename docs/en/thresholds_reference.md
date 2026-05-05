# Thresholds, weights, defaults — reference

> **Purpose:** one place to see **every numeric threshold that actually drives a decision in production**, where in the pipeline it kicks in, and why that specific value was chosen. If a number is not in this table, it does not gate any production behaviour.

> **Ukrainian version:** [`../ua/thresholds_reference.md`](../ua/thresholds_reference.md).

---

## Threshold map across the pipeline

```
GenerationRequest
    │
    │  ┌──── top_k = 5 ───────────────┐  thematic retrieval
    ▼  ▼                              │
┌──────────────────────┐              │
│ 1. RetrievalStage    │ ◄────────── theme corpus (153 poems, LaBSE)
└──────────────────────┘
    │
    │  ┌──── metric_examples_top_k = 2 (eval) / 3 (web) ───┐
    ▼  ▼                                                    │
┌──────────────────────┐                                    │
│ 2. MetricExamplesSt. │ ◄─────────────── metric-rhyme corpus (193, verified)
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 3. PromptStage       │ — builds the RAG prompt
└──────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. GenerationStage  ──► LLM Decorator Stack                         │
│                                                                     │
│   LoggingLLMProvider                                                │
│     RetryingLLMProvider     ← retry_max_attempts = 2,               │
│                              base 1.0 s, multiplier 2.0,            │
│                              max delay 10.0 s                       │
│       TimeoutLLMProvider    ← timeout_sec = 120.0                   │
│         SanitizingLLMProvider                                       │
│           ExtractingLLMProvider                                     │
│             GeminiProvider  ← temperature = 0.9,                    │
│                              max_output_tokens = 16384 (production) │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 5. ValidationStage   │
│                      │
│  PatternMeterValid.  ← allowed_mismatches = 2 per line
│  PhoneticRhymeValid. ← rhyme_threshold = 0.55 (normalised Levenshtein)
└──────────────────────┘
    │
    │ ok? → return
    │ violations?
    ▼
┌──────────────────────┐
│ 6. FeedbackLoopStage │ ← max_iterations: web=1, API=3, batch eval=1
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 7. FinalMetricsStage │ — runs 12 metric calculators (evaluation pipeline only)
└──────────────────────┘                                      │
                                                              ▼
                                                   estimated_cost_usd uses
                                                   gemini_input_price_per_m = 2.0,
                                                   gemini_output_price_per_m = 12.0
```

**Separate pipeline — detection** (`/api/poems/detect`, `make detect`):

```
poem_text
    │
    ▼
FirstLinesStanzaSampler  ← sample_lines = 4 — *precondition only*:
    │                       fewer than 4 non-empty lines → return (None, None);
    │                       otherwise the sampled chunk is discarded and
    │                       the FULL poem_text is forwarded to the detectors
    ▼
BruteForceMeterDetector(poem_text)
    ↑ sweeps (meter, feet) over feet_min..feet_max = 1..6
    ↑ the validator analyses every line of the poem; accepts when meter_accuracy ≥ 0.85
    │
    ▼
BruteForceRhymeDetector(poem_text)
    ↑ sweeps schemes ABAB/AABB/ABBA/AAAA on the full text
    ↑ accepts when rhyme_accuracy ≥ 0.5
```

---

## 1. Retrieval (RAG)

| Threshold | Value | Defined in | What it gates | Rationale |
|---|---|---|---|---|
| `top_k` (theme retriever) | `5` | [`SemanticRetriever.retrieve`](../../src/infrastructure/retrieval/semantic_retriever.py), [`GenerationRequest.top_k`](../../src/domain/models/commands.py) | How many semantically close excerpts go into the "thematic inspiration" prompt block | Trade-off: enough variety in style/lexicon so the LLM does not parrot one excerpt, but the prompt stays under ~4–5 K characters and fits Gemini Pro's `max_output_tokens` budget |
| `metric_examples_top_k` | `2` (evaluation) / `3` (`GenerationRequest` default) | [`evaluation_runner.py`](../../src/runners/evaluation_runner.py), [`commands.py`](../../src/domain/models/commands.py) | How many verified meter/rhyme reference quatrains go into the "meter reference" block | 2-3 is enough for a few-shot to anchor rhythm without rewriting whole quatrains. The signal duplicates information already in the structured `(meter, feet, scheme)` parameters |

---

## 2. LLM generation

| Threshold | Value | Defined in | What it gates | Rationale |
|---|---|---|---|---|
| `gemini_temperature` | `0.9` | [`AppConfig`](../../src/config.py), env `GEMINI_TEMPERATURE` | Generation creativity | A high value (≥ 0.8) prevents identical lines across calls. **For reasoning models (Gemini 2.5+ / 3.x Pro), drop to 0.3** — it cuts chain-of-thought leaking into output (ALL-CAPS syllables, `( - )` scansion). Production default keeps 0.9 for Flash compatibility |
| `gemini_max_tokens` | `16384` (production `.env`) / `8192` (fallback `AppConfig` default) / `4096` (`GeminiProvider.__init__` class default) | [`AppConfig`](../../src/config.py) and env `GEMINI_MAX_TOKENS`; production `.env` sets `16384` | Output token budget | Reasoning models (Pro 3.x) burn 4–6 K tokens on CoT *before* emitting `<POEM>...</POEM>`. At 4096 the envelope never lands — the model is cut off mid-reasoning. 8192 is the lower bound that still lets reasoning finish; **production `.env` runs `16384`** with the comment "16384 leaves headroom for chain-of-thought on reasoning-first Pro models" — i.e. extra buffer for longer reasoning runs and noisier responses |
| `timeout_sec` | `120.0` | [`LLMReliabilityConfig`](../../src/config.py), env `LLM_TIMEOUT_SEC` | Hard per-call deadline | Gemini Pro 2.5/3.x CoT runs 60–120 s/call; 120 s covers the upper end of legitimate reasoning. Beyond that the model has wandered and `TimeoutLLMProvider` should abort so the feedback iterator can move on. Drop to ~20 s for Flash |
| `retry_max_attempts` | `2` | [`LLMReliabilityConfig`](../../src/config.py), env `LLM_RETRY_MAX_ATTEMPTS` | Retries on `LLMError` | 2 balances "give transient 5xx / rate-limit one more shot" with "don't multiply paid attempts when the model is reliably broken". `LLMQuotaExceededError` short-circuits in [`ExponentialBackoffRetry.should_retry`](../../src/infrastructure/llm/decorators/retry_policy.py) — quota does not refresh inside the retry window |
| `retry_base_delay_sec` | `1.0` | `LLMReliabilityConfig` | First-failure backoff | Standard exp-backoff: enough for transient causes (rate-limit, network blip) to clear, short enough that the user does not notice |
| `retry_max_delay_sec` | `10.0` | `LLMReliabilityConfig` | Backoff ceiling | At multiplier=2 with attempts=2 only one 1-s delay actually fires — the 10-s ceiling is a safety net |
| `retry_multiplier` | `2.0` | `LLMReliabilityConfig` | Exp-backoff multiplier | Classic 2× — the standard in this domain, no exotic tuning |

---

## 3. Validation

| Threshold | Value | Defined in | What it gates | Rationale |
|---|---|---|---|---|
| `meter_allowed_mismatches` | `2` | [`ValidationConfig`](../../src/config.py) → [`PatternMeterValidator`](../../src/infrastructure/validators/meter/pattern_validator.py) | How many **real** (i.e. not pyrrhic/spondee-tolerated) stress mismatches are allowed per line | Classical poetry permits **rhythmic variation**: pyrrhics and spondees on weak / monosyllabic words are filtered out before counting (see [`meter_validation.md`](./meter_validation.md)). A `≤ 0` cutoff would reject canonical lines from Shevchenko, Lesia Ukrainka, Kostenko. `2` empirically passes the classical corpus and still catches genuine breakdowns |
| `rhyme_threshold` | `0.55` | [`ValidationConfig`](../../src/config.py) → [`PhoneticRhymeValidator`](../../src/infrastructure/validators/rhyme/phonetic_validator.py) | Minimum normalised Levenshtein similarity between two lines' IPA clausulae for the rhyme to count | Rhyme is not always exact (masculine / feminine, assonance, dissonance). 0.55 empirically passes canonical inexact rhymes in Ukrainian material (Shevchenko's "душу / мусиш" ≈ 0.5) but rejects pairs whose stress positions differ enough that the rhyme is gone |
| `bsp_score_threshold` | `0.6` | [`ValidationConfig`](../../src/config.py) → [`BSPMeterValidator`](../../src/infrastructure/validators/meter/bsp_validator.py) | Minimum composite BSP score for the **alternative** meter strategy | **Production does not use BSP** — `meter_validator()` returns `PatternMeterValidator`. BSP is an opt-in experimental strategy used in research. `0.6` is empirical on the verified corpus |
| `bsp_alternation_weight` | `0.50` | [`BSPAlgorithm.__init__`](../../src/infrastructure/validators/meter/bsp_algorithm.py) | Weight of "rhythm regularity" in the composite BSP score | Alternation is the strongest rhythm signal so it dominates at ½ the weight |
| `bsp_variation_weight` | `0.20` | same | Weight of "tolerance for variation" | Avoids penalising live rhythm for poetic-norm-range deviations |
| `bsp_stability_weight` | `0.15` | same | Weight of global pyramid stability | Deep pyramid levels are a weaker but non-zero signal |
| `bsp_balance_weight` | `0.15` | same | Weight of stress distribution across the line | Balances local vs global features |

> The BSP weights sum to 1.0 by design; changing one without redistributing the rest skews the [0, 1] normalisation of the composite score.

---

## 4. Feedback loop

| Threshold | Value | Defined in | What it gates | Rationale |
|---|---|---|---|---|
| `max_iterations` | `1` (web UI, batch eval), `3` (`GenerationRequest` default, API `/poems`) | [`evaluate.html`](../../src/handlers/web/templates/evaluate.html), [`schemas.py`](../../src/handlers/api/schemas.py), [`commands.py`](../../src/domain/models/commands.py) | How many times the feedback loop may ask the LLM to rewrite flagged lines after a validation failure | `1` — production default: each extra iteration costs another billed LLM call and adds 60–120 s of latency. Empirically the biggest gain comes from iteration 1; further iterations decay quickly. `3` is the upper bound enforced by API and the `evaluate.html` form (validation `ge=0, le=3`); beyond that the cost/quality trade is no longer worth it |

---

## 5. Detection (separate pipeline)

| Threshold | Value | Defined in | What it gates | Rationale |
|---|---|---|---|---|
| `detection.meter_min_accuracy` | `0.85` | [`DetectionConfig`](../../src/config.py) | Minimum fraction of valid lines for the classifier to commit to a `(meter, feet)` answer | Strict cutoff — the system says "this is iamb 4-foot" only when confident, otherwise returns "undetermined". Better silence than a close-but-wrong meter |
| `detection.rhyme_min_accuracy` | `0.5` | `DetectionConfig` | Minimum fraction of rhyming pairs | On a 4-line sample aggregate accuracy can only be 0.0 / 0.5 / 1.0. `0.5` admits a scheme as soon as one solid pair supports it (the other may be a slant rhyme like "душу / мусиш"). 0.75 would silently demand both pairs — too strict |
| `detection.sample_lines` | `4` | `DetectionConfig` | **Precondition gate in [`DetectionService.detect()`](../../src/services/detection_service.py)**: if the poem has fewer than `sample_lines` non-empty lines, the service returns `(None, None)` immediately and never invokes the detectors. The sampled chunk itself is **not used downstream** — the detectors receive the full `poem_text` and analyse every line | A quatrain is the shortest stanza that defines a rhyme scheme (`ABAB`/`AABB`/`ABBA`/`AAAA`); shorter poems make the brute-force sweep meaningless. The field is guarded by an assert in `DetectionConfig.__post_init__` because changing it would break the `IRhymeSchemeExtractor` contract |
| `detection.feet_min` / `detection.feet_max` | `1` / `6` | `DetectionConfig` | Foot-count sweep range | Matches the production generation/validation range — the system can recognise what it can produce. 1-foot anapest ("Мерехтить") is rare but legitimate; >6-foot lines barely exist in Ukrainian |

---

## 6. Cost estimation

| Threshold | Value | Defined in | What it gates | Rationale |
|---|---|---|---|---|
| `gemini_input_price_per_m` | `2.0` USD | [`AppConfig`](../../src/config.py), env `GEMINI_INPUT_PRICE_PER_M` | Per 1M input tokens used by the `estimated_cost_usd` metric | Published Gemini 3.1 Pro Preview rate (≤ 200 K context). Override when switching to Flash (where it's $0.075–$0.15/M) |
| `gemini_output_price_per_m` | `12.0` USD | same, env `GEMINI_OUTPUT_PRICE_PER_M` | Per 1M output tokens (incl. reasoning) | Reasoning tokens are billed as output — that's why the input/output spread is 1:6 |
| `delay_between_calls_sec` | `3.0` | [`BatchEvaluationService`](../../src/services/batch_evaluation_service.py), [`batch_evaluation_runner.py`](../../src/runners/batch_evaluation_runner.py) | Sleep between LLM calls in batch mode | Protects against Gemini rate-limit during 144 sequential calls (18 scenarios × 8 configs). 3 s empirically clears the free Gemini 2.5 Flash limit and is invisible on paid Pro tiers |

---

## How to change these values

1. **Via env vars** — for `gemini_*`, `LLM_*`, `OFFLINE_EMBEDDER`, `CORPUS_PATH`, `METRIC_EXAMPLES_PATH`. Full list in [`reliability_and_config.md`](./reliability_and_config.md).
2. **Via `AppConfig` fields** — for `validation.*` and `detection.*` (no env-binding yet; edit in code or inject a custom `AppConfig` in tests).
3. **Per-request override** — `top_k`, `metric_examples_top_k`, `max_iterations` arrive on `GenerationRequest` from the handler / runner; web and API forward form values.

> **Discipline:** any new threshold either lands here or lives locally as a `_PRIVATE_THRESHOLD` inside its module with a docstring rationale. Magic numbers without justification are off-limits (see ADRs under `docs/adr/`).
