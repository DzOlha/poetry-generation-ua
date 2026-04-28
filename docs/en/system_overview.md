# Ukrainian Poetry Generation System — detailed overview

> **Audience:** developers, researchers, reviewers who want to understand how the system works end-to-end — from a user request to the final poem and quality metrics.

> **Ukrainian version:** [`../ua/system_overview.md`](../ua/system_overview.md).
>
> **Companion documents** (neighbouring files in this folder):
> - Start here: [reader-oriented overview](./system_overview_for_readers.md) ([UA](../ua/system_overview_for_readers.md))
> - Algorithms: [stress and syllables](./stress_and_syllables.md), [metre validation](./meter_validation.md), [rhyme validation](./rhyme_validation.md), [detection](./detection_algorithm.md)
> - RAG and prompts: [semantic retrieval](./semantic_retrieval.md), [prompt construction](./prompt_construction.md)
> - Feedback loop + LLM integration: [feedback loop](./feedback_loop.md), [sanitization](./sanitization_pipeline.md), [LLM decorator stack](./llm_decorator_stack.md), [reliability & config](./reliability_and_config.md)
> - Research: [evaluation harness](./evaluation_harness.md) — 18 scenarios × 8 ablation configs

---

## Contents

0. [Architectural decisions and patterns (OOP/SOLID/DDD)](#0-architectural-decisions-and-patterns-oopsoldddd)
1. [High-level architecture](#1-high-level-architecture)
2. [Component 1 — Corpus and data loading](#2-component-1--corpus-and-data-loading)
3. [Component 2 — Semantic retriever (LaBSE)](#3-component-2--semantic-retriever-labse)
4. [Component 3 — Metric examples retriever](#4-component-3--metric-examples-retriever)
5. [Component 4 — Prompt construction (RAG)](#5-component-4--prompt-construction-rag)
6. [Component 5 — LLM client (Gemini)](#6-component-5--llm-client-gemini)
7. [Component 6 — Stress dictionary (UkrainianStressDict)](#7-component-6--stress-dictionary-ukrainianstressdict)
8. [Component 7 — Metre validator](#8-component-7--metre-validator)
9. [Component 8 — Rhyme validator](#9-component-8--rhyme-validator)
10. [Generation and regeneration cycle (Feedback Loop)](#10-generation-and-regeneration-cycle-feedback-loop)
11. [Quality metrics — formulas and rationale](#11-quality-metrics--formulas-and-rationale)
12. [Evaluation Harness and ablation configs](#12-evaluation-harness-and-ablation-configs)
13. [Test scenarios](#13-test-scenarios)
14. [Pipeline tracing (PipelineTrace)](#14-pipeline-tracing-pipelinetrace)
15. [Environment variables and settings](#15-environment-variables-and-settings)
16. [Data flow diagram](#16-data-flow-diagram)

---

## 0. Architectural decisions and patterns (OOP/SOLID/DDD)

The system is built according to **Domain-Driven Design (DDD)**, **SOLID**, and classical design-pattern principles.

### Layer structure

```
src/
├── domain/              ← Domain layer (value objects, entities, aggregates, ports)
│   ├── models/          ← MeterSpec, RhymeScheme, Poem, GenerationRequest,
│   │                      LineFeedback, PairFeedback, CorpusEntry, MetricCorpusEntry, ...
│   ├── ports/           ← 30+ abstract interfaces (ILLMProvider, IMeterValidator,
│   │                      IClock, IDelayer, IStressPatternAnalyzer, ...)
│   ├── values.py        ← MeterName, RhymePattern enums
│   ├── errors.py        ← DomainError hierarchy (each subclass owns http_status_code)
│   └── evaluation.py    ← AblationConfig, PipelineTrace
├── services/            ← Application layer (PoetryService, EvaluationService,
│                          BatchEvaluationService, DetectionService)
├── infrastructure/      ← Concrete implementations of ports
│   ├── composition/     ← DI sub-containers (primitives, validation, generation,
│   │                      metrics, evaluation, detection — each split into focused files)
│   ├── clock/           ← SystemClock / SystemDelayer (IClock / IDelayer adapters)
│   ├── llm/             ← GeminiProvider, MockLLMProvider, decorator stack (5 tiers)
│   ├── http/            ← DefaultHttpErrorMapper (polymorphic dispatch on DomainError)
│   ├── sanitization/    ← SentinelPoemExtractor, RegexPoemOutputSanitizer
│   ├── validators/      ← Meter (Pattern), Rhyme (Phonetic), Composite
│   ├── stages/          ← Pipeline stages
│   ├── pipeline/        ← SequentialPipeline, StageFactory
│   ├── reporting/       ← MarkdownReporter façade + TableFormatter / TraceFormatter
│   │                      / CostCalculator / MarkdownDocumentBuilder collaborators
│   ├── tracing/         ← PipelineTracer, InMemoryLLMCallRecorder (for UI tracing)
│   └── ...              ← embeddings, retrieval, repositories, prompts, metrics, ...
├── handlers/            ← Transport adapters (FastAPI, Web UI)
├── runners/             ← IRunner implementations for scripts
├── shared/              ← Cross-cutting pure utilities
├── config.py            ← AppConfig (frozen, from env vars)
└── composition_root.py  ← Thin Container façade composing the sub-containers
```

### Domain model

**Value Objects** (immutable, identity by value):

| Class | File | Purpose |
|-------|------|---------|
| `MeterSpec` | `domain/models/specifications.py` | Metre + foot count |
| `RhymeScheme` | `domain/models/specifications.py` | Rhyme scheme (ABAB, AABB, …) |
| `PoemStructure` | `domain/models/specifications.py` | Stanza × lines count |
| `Poem` | `domain/models/aggregates.py` | Parsed poem aggregate |

**Commands / DTOs** (inter-layer data transfer objects):

| Class | File | Purpose |
|-------|------|---------|
| `GenerationRequest` | `domain/models/commands.py` | Full generation request |
| `ValidationRequest` | `domain/models/commands.py` | Validation request |
| `ValidationResult` | `domain/models/results.py` | Metre + rhyme validation result |
| `GenerationResult` | `domain/models/results.py` | Final result: poem + validation |

`GenerationRequest` replaces a long parameter list. Instead of dozens of arguments:
```python
service.generate(request)  # a single GenerationRequest object
```

**Abstract ports** (`domain/ports/`) — interfaces for the infrastructure layer:

| Interface | Concrete implementation |
|-----------|-------------------------|
| `IThemeRepository` | `JsonThemeRepository`, `DemoThemeRepository` |
| `IMetricRepository` | `JsonMetricRepository` |
| `IRetriever` | `SemanticRetriever` (LaBSE cosine similarity) |
| `IPromptBuilder` | `RagPromptBuilder` |
| `IRegenerationPromptBuilder` | `NumberedLinesRegenerationPromptBuilder` |
| `IMeterValidator` | `PatternMeterValidator` |
| `IRhymeValidator` | `PhoneticRhymeValidator` |
| `IPoemValidator` | `CompositePoemValidator` (metre + rhyme) |
| `ILLMProvider` | `GeminiProvider`, `MockLLMProvider` + decorator stack (Logging → Retry → Timeout → Sanitizing → Extracting) |
| `IPoemExtractor` | `SentinelPoemExtractor` (`<POEM>…</POEM>` extraction) |
| `IPoemOutputSanitizer` | `RegexPoemOutputSanitizer` (allowlist sanitization) |
| `ILLMCallRecorder` | `InMemoryLLMCallRecorder` (raw/extracted/sanitized for UI tracing) |
| `IEmbedder` | `LaBSEEmbedder`, `OfflineDeterministicEmbedder`, `CompositeEmbedder` |
| `IStressDictionary` | `UkrainianStressDict` |
| `IPhoneticTranscriber` | `UkrainianIpaTranscriber` |
| `IClock` / `IDelayer` | `SystemClock` / `SystemDelayer` (real-time), `FakeClock` / `FakeDelayer` (tests) |
| `IHttpErrorMapper` | `DefaultHttpErrorMapper` (polymorphic dispatch on `DomainError.http_status_code`) |

### Design patterns

| Pattern | Where applied |
|---------|---------------|
| **Strategy** | `IMeterValidator` (Pattern), `IRhymeValidator`, `IStageSkipPolicy` |
| **Repository** | `IThemeRepository`, `IMetricRepository` |
| **Factory** | `ILLMProviderFactory`, `IStageFactory`, `ITracerFactory` |
| **Dependency Injection** | Constructor injection; `composition_root.Container` |
| **Decorator** | LLM reliability + output cleaning: `Logging → Retry → Timeout → Sanitizing → Extracting` |
| **Composite** | `CompositeEmbedder` (primary + fallback), `CompositePoemValidator` (metre + rhyme) |
| **Null Object** | `NullTracer`, `NullLogger` |
| **Registry** | `IMetricCalculatorRegistry`, `IScenarioRegistry` |

### SOLID principles

- **S** (SRP): `PoetryService` orchestrates; `CompositePoemValidator` validates; `RagPromptBuilder` builds prompts; each sub-container wires one slice of the graph. `MarkdownReporter` is a thin façade over four collaborators (`TableFormatter`, `TraceFormatter`, `CostCalculator`, `MarkdownDocumentBuilder`) so each reporting concern lives in its own class.
- **O** (OCP): a new validator or retriever strategy plugs in via an interface without touching the pipeline. `DefaultHttpErrorMapper` adds new domain-error → HTTP mappings purely by extension — each `DomainError` subclass advertises its own `http_status_code` and class-name `http_error_type`, so the mapper has no `isinstance` chain to grow.
- **L** (LSP): contract tests (`tests/contracts/`) guarantee implementation substitutability — including every LLM decorator and the full stack (see `tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py`).
- **I** (ISP): 30+ narrow interfaces instead of a few wide ones (separate `ILineSplitter`, `ITokenizer`, `IStringSimilarity`; the legacy wide `IProsodyAnalyzer` is now deprecated in favour of `IStressPatternAnalyzer` + `IExpectedMeterBuilder` + `IMismatchTolerance`).
- **D** (DIP): services depend only on abstractions (`domain/ports/`); concrete classes are wired in `composition_root.py`. Time and sleep are abstracted behind `IClock` / `IDelayer` so `EvaluationService` and `BatchEvaluationService` never call `time.perf_counter` or `time.sleep` directly — tests inject `FakeClock` / `FakeDelayer`.

---

## 1. High-level architecture

The system is a **RAG pipeline** (Retrieval-Augmented Generation) for Ukrainian poetry generation with specified prosodic parameters. It has five sequential stages:

```
Input: GenerationRequest (theme, MeterSpec, RhymeScheme, PoemStructure, max_iterations)
        │
        ▼
┌────────────────┐
│ 1. Retrieval   │  ← SemanticRetriever finds semantically close poems (LaBSE)
│    Stage       │     corpus/uk_theme_reference_corpus.json, 768-dim vectors
└────────────────┘
        │  top-k ThemeExcerpt (thematic inspiration)
        ▼
┌────────────────┐
│ 2. Metric      │  ← JsonMetricRepository finds reference poems
│ Examples Stage │     corpus/uk_metric-rhyme_reference_corpus.json
└────────────────┘
        │  top-k MetricExample (rhythm template)
        ▼
┌────────────────┐
│ 3. Prompt      │  ← RagPromptBuilder assembles a structured prompt:
│    Stage       │     thematic examples + metric references + form parameters
└────────────────┘
        │  prompt string
        ▼
┌────────────────┐
│ 4. Generation  │  ← GeminiProvider through the 5-tier decorator stack
│    Stage       │     (Logging → Retry → Timeout → Sanitizing → Extracting → Gemini)
└────────────────┘
        │  poem text
        ▼
┌────────────────┐
│ 5. Validation  │  ← CompositePoemValidator checks metre (PatternMeterValidator)
│    Stage       │     and rhyme (PhoneticRhymeValidator) via syllables/stress
└────────────────┘
        │  ok? → return poem
        │  violations? → build feedback
        ▼
┌────────────────┐
│ 6. Feedback    │  ← ValidatingFeedbackIterator: re-generate the flagged lines
│ Loop Stage     │     (up to max_iterations; stops on valid or limit)
└────────────────┘
        │
        ▼
Output: GenerationResult(poem, ValidationResult(metre, rhyme, iterations))
```

**Key idea:** the LLM doesn't know prosody rules explicitly. The system compensates with **symbolic post-generation validation** and **targeted feedback** that points at exact error positions. This makes the approach extensible: rules live in `validator.py`, not in the prompt.

---

## 2. Component 1 — Corpus and data loading

**Files:** `src/infrastructure/repositories/theme_repository.py`, `src/domain/models/corpus_entry.py`

### `CorpusEntry` shape

```python
class CorpusEntry(TypedDict, total=False):
    id: str                          # unique identifier
    text: str                        # full poem text
    author: str                      # author
    approx_theme: list[str]          # theme tags
    source: str                      # source
    lines: int                       # line count
    title: str                       # poem title
    path: str                        # source file path
    embedding: list[float]           # pre-computed LaBSE vector (768-dim, optional)
```

### Corpus sources

| Class / Function | Source | Purpose |
|---|---|---|
| `JsonThemeRepository` | `CORPUS_PATH` env → default `corpus/uk_theme_reference_corpus.json` | Theme corpus (153 poems) + LaBSE embeddings |
| `DemoThemeRepository` | hard-coded poems in code | Fallback when the file is missing |
| `JsonMetricRepository` | `METRIC_EXAMPLES_PATH` env → `corpus/uk_metric-rhyme_reference_corpus.json` | Metre + rhyme reference examples (38 verified records) |

### Loading the corpus

The theme corpus loads via `JsonThemeRepository` (implements `IThemeRepository`), which reads the JSON file at `AppConfig.corpus_path` (default `corpus/uk_theme_reference_corpus.json`). If the file is missing, `DemoThemeRepository` returns a hard-coded fallback corpus.

**Why this is needed:** the corpus is a knowledge base for RAG. Without real poetry examples the LLM generates detached from any style.

### The `embedding` field in JSON

Every poem in `uk_theme_reference_corpus.json` has a **pre-computed 768-dim LaBSE vector**. The retriever uses it directly **without re-encoding** on every request — this fully eliminates runtime overhead for encoding the corpus.

Embeddings are computed and persisted by a script:

```bash
# One step: build theme corpus + embeddings
make build-theme-corpus-with-embeddings

# Or embeddings only for an existing corpus (idempotent — skips poems that already have them)
make embed-theme-corpus
# python3 scripts/build_corpus_embeddings.py --corpus corpus/uk_theme_reference_corpus.json
```

---

## 3. Component 2 — Semantic retriever (LaBSE)

**File:** `src/infrastructure/retrieval/semantic_retriever.py` (implements `IRetriever`)
**Embedder:** `src/infrastructure/embeddings/labse.py` → `LaBSEEmbedder` (implements `IEmbedder`)
**Stage:** `src/infrastructure/stages/retrieval_stage.py` → `RetrievalStage`

### Why we need a retriever

The goal is to find corpus poems that are **semantically close to the request theme** and feed them to the LLM as thematic inspiration. Classical RAG: instead of the LLM relying purely on parameters, it sees concrete examples.

### What LaBSE is

**LaBSE** (Language-agnostic BERT Sentence Embeddings, Google, 2020) is a transformer model (~1.8 GB) producing language-independent sentence embeddings.

**Architecture:**
- Base: 12-layer BERT transformer
- Trained jointly on two tasks:
  1. **MLM** (Masked Language Model) — standard BERT training, gives language understanding
  2. **TLM** (Translation Language Model) — training on 6B+ parallel translations across 109 languages, gives cross-lingual alignment

**Output:** a 768-dim vector on the unit sphere (after L2 normalisation). Two sentences with similar meaning — even in different languages — have vectors with a **high cosine dot product** (close to 1.0). Unrelated texts land near 0 or below.

**Why LaBSE over alternatives:**
- Trained specifically on **sentence-level similarity**, not token-level
- Good Ukrainian support (Cyrillic is in the WordPiece vocabulary)
- Vectors are geometrically meaningful: proximity = semantic similarity

### `retrieve()` algorithm

```
1. encode(theme_description)  →  theme_vec  [768 float]
        ↓
2. For every poem in the corpus:
   a) take poem.embedding (pre-computed, always present) → poem_vec
   b) if embedding missing (legacy corpus) → encode(poem.text) on-the-fly
   c) cosine_similarity(theme_vec, poem_vec)
        ↓
3. Sort by descending similarity
        ↓
4. Return top-k (default 5) nearest
```

For the current `uk_theme_reference_corpus.json`, step 2b **never triggers** — all 153 poems have pre-computed vectors.

### Cosine similarity

```python
dot  = sum(a * b for a, b in zip(theme_vec, poem_vec))
norm_a = sqrt(sum(a*a for a in theme_vec))
norm_b = sqrt(sum(b*b for b in poem_vec))
sim = dot / (norm_a * norm_b)   # ∈ [-1, 1]
```

Because vectors are L2-normalised (`normalize_embeddings=True`), `norm_a = norm_b = 1`, so `sim = dot` — just a dot product.

### Fallback without LaBSE — `OfflineDeterministicEmbedder`

**File:** `src/infrastructure/embeddings/offline.py`

When the model fails to load or `OFFLINE_EMBEDDER=true`:

```python
# Deterministic pseudo-random vector based on text hash
rng = random.Random(abs(hash(text)) % (2**32))
return [rng.gauss(0.0, 1.0) for _ in range(768)]
```

The same text always yields the same vector, but there's **no semantic meaning** — intended for tests without API access.

`CompositeEmbedder` (`src/infrastructure/embeddings/composite.py`) implements the Composite Pattern: tries primary (`LaBSEEmbedder`), falls back on error (`OfflineDeterministicEmbedder`).

---

## 4. Component 3 — Metric examples retriever

**File:** `src/infrastructure/repositories/metric_repository.py` (implements `IMetricRepository`)
**Model:** `src/domain/models/entities.py` → `MetricExample`
**Stage:** `src/infrastructure/stages/metric_examples_stage.py` → `MetricExamplesStage`

### Why we need it

The semantic retriever finds thematically close poems but does not guarantee they match the requested **metre and rhyme scheme**. The metric retriever solves a different problem: find reference poems that exactly match the requested metre, foot count, and rhyme scheme. These examples are added to the prompt as a **rhythm and rhyme reference** for the LLM.

### `MetricExample` shape

```python
@dataclass(frozen=True)
class MetricExample:
    id: str           # unique identifier (e.g. "iamb_4_ABAB_shevchenko")
    meter: str        # "ямб", "хорей", "дактиль", "амфібрахій", "анапест"
    feet: int         # foot count
    scheme: str       # "ABAB", "AABB", "ABBA", "AAAA"
    text: str         # full example text
    verified: bool    # True = manually verified reference
    author: str       # author
    note: str         # notes
```

Data is stored as `MetricCorpusEntry` (TypedDict, `src/domain/models/metric_corpus_entry.py`) and converted to `MetricExample` entities on load.

### Dataset `corpus/uk_metric-rhyme_reference_corpus.json`

Contains reference poems with explicit metre, foot, and rhyme scheme annotations from classical authors:

| Metre | Examples |
|-------|----------|
| iamb | Shevchenko "Реве та стогне…" (4-foot, ABAB) |
| trochee | Chuprynka (4-foot, ABAB) |
| dactyl | Skovoroda (4-foot, AABB) |
| amphibrach | Sosyura (4-foot, ABAB) |
| anapest | Lesya Ukrainka, Kostenko (3-foot, ABAB) |

### `JsonMetricRepository.query()` algorithm

```python
class JsonMetricRepository(IMetricRepository):
    def query(self, meter: str, feet: int, scheme: str,
              top_k: int = 3) -> list[MetricExample]:
        # 1. Normalise metre name via MeterCanonicalizer
        #    "iamb" → "ямб", "trochee" → "хорей", ...
        meter_ua = self._canonicalizer.canonicalize(meter)

        # 2. Exact-match filter: meter + feet + scheme
        matched = [e for e in self._entries if
                   e.meter.lower() == meter_ua and
                   e.feet == feet and
                   e.scheme.upper() == scheme.upper()]

        # 3. Verified examples first
        matched = sorted(matched, key=lambda e: (not e.verified,))

        return matched[:top_k]
```

**Key properties:**
- Returns `[]` if the file is missing (doesn't throw)
- English aliases supported: `iamb/trochee/dactyl/amphibrach/anapest`
- `verified_only=True` — returns only manually verified examples
- Verified examples are sorted before unverified ones

---

## 5. Component 4 — Prompt construction (RAG)

**File:** `src/infrastructure/prompts/rag_prompt_builder.py`
**Port:** `src/domain/ports/prompts.py` → `IPromptBuilder`

`RagPromptBuilder` implements `IPromptBuilder` and assembles a prompt from thematic examples (from `SemanticRetriever`), metric references (from `JsonMetricRepository`), and form parameters (from `GenerationRequest`). It runs through `PipelineState`:

```python
class RagPromptBuilder(IPromptBuilder):
    def build(self, state: PipelineState) -> str:
        excerpts = "\n".join(item.text.strip() for item in state.retrieved)
        total_lines = state.request.structure.stanza_count * state.request.structure.lines_per_stanza
        structure = (
            f"{state.request.structure.stanza_count} stanza(s) "
            f"of {state.request.structure.lines_per_stanza} lines each ({total_lines} lines total)"
        )
        metric_section = ""
        if state.metric_examples:
            examples_text = "\n\n".join(e.text.strip() for e in state.metric_examples)
            metric_section = (
                f"\nUse these verified examples as METER and RHYME reference "
                f"(they demonstrate {meter} meter with {rhyme_scheme} rhyme scheme — "
                f"follow this rhythm and rhyme pattern exactly):\n"
                f"{examples_text}\n"
            )
        return (
            "Use the following poetic excerpts as thematic inspiration (do not copy):\n"
            f"{excerpts}\n{metric_section}\n"
            f"Theme: {theme}\nMeter: {meter}\nRhyme scheme: {rhyme_scheme}\n"
            f"Structure: {structure}\nGenerate a Ukrainian poem with exactly {total_lines} lines."
        )
```

### Prompt structure (with metric examples)

```
Use the following poetic excerpts as thematic inspiration (do not copy):
[corpus poem 1 — semantically close to the theme]
[corpus poem 2]
...

Use these verified examples as METER and RHYME reference
(they demonstrate ямб meter with ABAB rhyme scheme — follow this rhythm and rhyme pattern exactly):
[verified reference 1 — Shevchenko]
[verified reference 2]

Theme: весна у лісі, пробудження природи
Meter: ямб
Rhyme scheme: ABAB
Structure: 2 stanzas of 4 lines each (8 lines total)
Generate a Ukrainian poem with exactly 8 lines.
```

**Two sections, two purposes:**
- **Thematic examples** (from the semantic retriever): lexicon, imagery, tone.
- **Metric examples** (from the metric retriever): an exact rhythm + rhyme template to reproduce.

### Structure parameters

`stanza_count` and `lines_per_stanza` come from the `EvaluationScenario` (or are overridden via `--stanzas` / `--lines-per-stanza` CLI / Makefile). The product `stanza_count × lines_per_stanza = total_lines` is passed to the LLM as a hard requirement.

**Why "do not copy":** without this instruction the LLM sometimes reproduces a corpus poem verbatim. We want thematic inspiration, not plagiarism.

**A system instruction** is passed separately via `system_instruction` in `GeminiProvider`:
```
You are a Ukrainian poetry generator. Return only the poem text, no explanations, no markdown.
```

This gives the LLM a clear role context and suppresses extraneous output (comments, explanations, markdown).

**Regeneration prompt:** feedback-loop iterations use `NumberedLinesRegenerationPromptBuilder` — the poem is passed with line numbers, violations as a bullet list. Details in [`prompt_construction.md`](./prompt_construction.md).

**Sentinel envelope:** both prompts require the model to wrap its final poem in `<POEM>…</POEM>` so extraction can separate the poem from chain-of-thought. See [`sanitization_pipeline.md`](./sanitization_pipeline.md).

---

## 6. Component 5 — LLM client (Gemini)

**File:** `src/infrastructure/llm/gemini.py`

### `ILLMProvider` abstraction

```python
class ILLMProvider(ABC):
    def generate(self, prompt: str, max_tokens: int) -> str: ...
```

A single `generate` operation that produces text from a prompt. Initial generation uses the RAG prompt; regeneration uses the feedback prompt with the violation list.

### `GeminiProvider` — the real provider

Uses the **new `google.genai` SDK** (not the deprecated `google.generativeai`):

```python
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-3.1-pro-preview",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.9,          # high: more creativity
        max_output_tokens=8192,   # ≥ 8192 is mandatory for reasoning models
        system_instruction=...,
    ),
)
```

**Parameters (current defaults):**
- `temperature=0.9` — relatively high so the generation is varied and doesn't repeat identical lines. For reasoning models (Gemini 2.5+ / 3.x Pro) reducing to `0.3` is recommended — it curbs CoT leakage into the output.
- `max_output_tokens=8192` — must be ≥ 8192 on reasoning models; otherwise the chain-of-thought consumes the budget before the `<POEM>` envelope is emitted.
- `model="gemini-3.1-pro-preview"` — default. Paid model; the best quality for Ukrainian poetry. Alternatives: `gemini-2.5-pro` (slightly cheaper), `gemini-2.5-flash` (free tier, but noticeably worse quality for poetry).
- `thinking_config` — if `GEMINI_DISABLE_THINKING=true` the provider passes `ThinkingConfig(thinking_budget=0, include_thoughts=False)`. Supported by Gemini 2.5; Gemini 3.x Pro preview rejects it with HTTP 400.

### `MockLLMProvider` — test stub

Returns a fixed poem without calling the API. Lets us test the pipeline without burning API quota.

### LLM reliability decorators (the full 5-layer stack)

The real `GeminiProvider` is wrapped by a decorator stack (Decorator Pattern). Outermost → innermost:

```
LoggingLLMProvider              ← structured log per call + duration
  └─ RetryingLLMProvider        ← exponential backoff on LLMError (up to retry_max_attempts)
      └─ TimeoutLLMProvider     ← hard deadline (timeout_sec)
          └─ SanitizingLLMProvider   ← allowlist sanitization; empty → LLMError
              └─ ExtractingLLMProvider ← extract poem from <POEM>…</POEM> envelope
                  └─ GeminiProvider   ← real Gemini API call
```

- **`LoggingLLMProvider`** — structured INFO/ERROR logs; sees the original arguments and the final result (post-retry).
- **`RetryingLLMProvider`** — retries on `LLMError`. A timeout is an `LLMError`, so it is retried (often pointlessly — the model stays equally slow).
- **`TimeoutLLMProvider`** — runs the inner call in a daemon thread; on `timeout_sec` overrun raises `LLMError`. **The thread is not killed** — Python can't force-terminate one; the actual HTTP call to Gemini keeps running.
- **`SanitizingLLMProvider`** — feeds output through `IPoemOutputSanitizer`. An empty result (all garbage) raises `LLMError`, giving the retry layer another shot. Writes sanitized text to `ILLMCallRecorder` for UI tracing.
- **`ExtractingLLMProvider`** — extracts the content between `<POEM>…</POEM>` via `IPoemExtractor`. Missing tags → passes input through (sanitizer will salvage). Writes raw and extracted text to `ILLMCallRecorder`.

Configuration lives in `LLMReliabilityConfig` inside `AppConfig` (see §15). Sanitiser and extractor are detailed in [`sanitization_pipeline.md`](./sanitization_pipeline.md); the decorator stack in [`llm_decorator_stack.md`](./llm_decorator_stack.md).

### LLM output sanitization

Reasoning models frequently leak chain-of-thought into the final output: scansion notation (`КрОки`, `(u u -)`), syllable-hyphenated words (`за-гу-бив-ся`), English commentary, bullet-pointed explanations. The system has a two-layer defence:

1. **Sentinel extraction** — the model is asked to wrap the final poem in `<POEM>…</POEM>` tags. `SentinelPoemExtractor` ([`src/infrastructure/sanitization/sentinel_poem_extractor.py`](../../src/infrastructure/sanitization/sentinel_poem_extractor.py)) tolerates common failures: multiple blocks → take the last (usually the final revision after CoT); opening tag without a closing one → take everything after the last `<POEM>` (`max_tokens`-truncated output); no tags → pass the input to the sanitizer.

2. **Allowlist sanitization** — `RegexPoemOutputSanitizer` ([`src/infrastructure/sanitization/regex_poem_output_sanitizer.py`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py)) examines every line character-by-character: allowed only Ukrainian Cyrillic letters, combining acute accent, apostrophe, punctuation (. , ! ? : ; …), dash / hyphen, quotes (« » „ " " " '), parentheses, whitespace. Everything else (Latin letters, digits, `|`, `/`, `\`, `<>`, `[]`, `=`, emoji) automatically disqualifies the line. Three additional behavioural checks: at least one Cyrillic letter; no lowercase→uppercase inside a token (`КрО`); no ≥ 2 intra-word hyphens (`за-гу-бив-ся`).

Full algorithm + the "salvage pass" for parenthesised scansion chunks — in [`sanitization_pipeline.md`](./sanitization_pipeline.md).

### LLM call tracing

For UI rendering (generation and ablation-evaluation pages), both sanitization decorators write to `ILLMCallRecorder` ([`src/domain/ports/llm_trace.py`](../../src/domain/ports/llm_trace.py); implementation `InMemoryLLMCallRecorder` in [`src/infrastructure/tracing/llm_call_recorder.py`](../../src/infrastructure/tracing/llm_call_recorder.py)):

- `record_raw(text)` — the original Gemini response (ExtractingLLMProvider input)
- `record_extracted(text)` — text after `<POEM>…</POEM>` extraction (ExtractingLLMProvider output)
- `record_sanitized(text)` — text after allowlist filtering (SanitizingLLMProvider output)

`ValidationStage` (iteration 0) and `ValidatingFeedbackIterator` (iterations 1+) read the recorder snapshot and store it in `IterationRecord.raw_llm_response` / `.sanitized_llm_response`. The UI renders both fields under a collapsible "LLM trace (raw / sanitized)" block.

### LLM provider selection

`ILLMProviderFactory` (concrete: `DefaultLLMProviderFactory`) picks the provider automatically:
- If `GEMINI_API_KEY` is set → `GeminiProvider` (with the full 5-tier decorator stack)
- Otherwise → `MockLLMProvider` (deterministic stub)

Selection happens in `composition_root.py` when the dependency container is built. `GenerationSubContainer` is now a thin façade composing three focused sub-containers — `GenerationDataPlaneSubContainer` (repositories, embedder, retriever), `LLMStackSubContainer` (factory + reliability decorators), and `PipelineStagesSubContainer` (prompts, feedback loop, pipeline) — each in its own module under `src/infrastructure/composition/`.

---

## 7. Component 6 — Stress dictionary (UkrainianStressDict)

**File:** `src/infrastructure/stress/ukrainian.py`, port: `src/domain/ports/stress.py`

### Why it's needed

To validate metre we need to know **which syllable carries the stress in each word**. Ukrainian has free stress (no fixed rule), so an external resource is required.

### Implementation

`UkrainianStressDict` implements the `IStressDictionary` interface:

```python
class UkrainianStressDict(IStressDictionary):
    on_ambiguity: str = "first"   # what to do with homographs: "first" / "random"

    def __post_init__(self):
        from ukrainian_word_stress import Stressifier, StressSymbol
        self._stressify = Stressifier(
            stress_symbol=StressSymbol.CombiningAcuteAccent,
            on_ambiguity=self.on_ambiguity,
        )
```

The `ukrainian-word-stress` library uses **Stanza NLP** (Stanford NLP Group) for morphological analysis, which downloads ~500 MB of models on first run.

### `get_stress_index(word) → int | None`

1. Calls `self._stressify(word)` → returns the word with a Unicode combining acute `\u0301` after the stressed vowel.
2. Walks characters, counts vowels, finds where the accent sits → returns the **0-based index of the stressed vowel** among all vowels in the word.

**Example:** `"лі́с"` → stress on the 0th vowel → `index = 0`; `"весна́"` → on the 1st → `index = 1`.

### Fallback — `PenultimateFallbackStressResolver`

**File:** `src/infrastructure/stress/penultimate_resolver.py`

Implements `IStressResolver`. If `UkrainianStressDict` can't determine the stress (unknown word) the fallback **places stress on the penultimate syllable** (statistically the most frequent position in Ukrainian).

### Syllable counter — `SyllableCounter`

**File:** `src/infrastructure/stress/syllable_counter.py`

Implements `ISyllableCounter`. Counts vowels in a word to determine syllable count.

---

## 8. Component 7 — Metre validator

**Files:** `src/infrastructure/validators/meter/pattern_validator.py`
**Port:** `src/domain/ports/validation.py` → `IMeterValidator`

### Supported metres

**Templates file:** `src/infrastructure/meter/ukrainian_meter_templates.py` (implements `IMeterTemplateProvider`)

```python
METER_TEMPLATES = {
    "ямб":        ["u", "—"],       # stress on an even syllable
    "хорей":      ["—", "u"],       # stress on an odd syllable
    "дактиль":    ["—", "u", "u"],  # ternary foot
    "амфібрахій": ["u", "—", "u"],
    "анапест":    ["u", "u", "—"],
}
```

`"—"` = stressed position, `"u"` = unstressed.

**Metre name canonicalisation:** `MeterCanonicalizer` (`src/infrastructure/meter/meter_canonicalizer.py`) normalises English and Ukrainian aliases: `"iamb"` → `"ямб"`, `"trochee"` → `"хорей"`, etc.

### Line validation algorithm (`PatternMeterValidator`)

**Step 1 — Tokenise the line:**
```python
tokens = tokenize_line_ua(line)
# → LineTokens(words=["весна", "прийшла", ...], syllables_per_word=[2, 3, ...])
```
`tokenize_line_ua` pulls words via the regex `[а-яіїєґʼ'-]+`, counts vowels per word.

**Step 2 — Expected pattern:**
```python
expected = build_expected_pattern("ямб", foot_count=4)
# → ["u","—","u","—","u","—","u","—"]  (4 feet × 2 symbols = 8 positions)
```

**Step 3 — Actual stress pattern:**
For each word: resolve stress via `UkrainianStressDict` (implements `IStressDictionary`), mark `"—"` at the corresponding syllable position in the overall array, the rest remains `"u"`.

```
"Весна  прийшла  у  ліс  зелений"
  2 syl  3 syl   1   1    3 syl       ← syllables_per_word
  [u,—]  [u,—,u] [u] [—]  [u,—,u]     ← actual stress positions
→ actual = [u,—, u,—,u, u, —, u,—,u]
```

**Step 4 — Tolerant comparison with rhythmic substitutions:**

```python
n = min(len(actual), len(expected))
raw_errors = [i + 1 for i in range(n) if actual[i] != expected[i]]

# Filter out allowed rhythmic substitutions
real_errors = [pos for pos in raw_errors
               if not _is_tolerated_mismatch(pos - 1, actual, expected, flags)]

length_ok = _line_length_ok(actual, expected)
ok = len(real_errors) <= allowed_mismatches and length_ok
```

**Allowed rhythmic deviations:**

| Substitution | Tolerance condition | Explanation |
|-------------|---------------------|-------------|
| **Pyrrhic** (expected `—`, got `u`) | monosyllabic or function word | prepositions, conjunctions, particles, pronouns |
| **Spondee** (expected `u`, got `—`) | monosyllabic or function word | a secondary stress is natural for such words |

**Function words** (defined in `src/infrastructure/meter/ukrainian_weak_stress_lexicon.py`): ~50 items — prepositions (`в`, `на`, `до` …), conjunctions (`і`, `та`, `що` …), particles (`не`, `б`, `же` …), personal pronouns (`я`, `ти`, `він` …), possessive pronouns (`мій`, `твій`, `свій` …). Syllable classification is in `SyllableFlagStrategy` (`src/infrastructure/meter/syllable_flag_strategy.py`).

**Line-length tolerances (`_line_length_ok`):**

| Delta | Condition | Name |
|-------|-----------|------|
| `+1` | last syllable `u` | feminine ending |
| `+2` | last two syllables `u u` | dactylic ending |
| `-1 ≤ diff < 0` for binary feet (iamb, trochee) | unconditional | catalexis |
| `-2 ≤ diff < 0` for ternary feet (dactyl, amphibrach, anapest) | unconditional | catalexis |

A deviation `|diff| ≥ foot_size` means an entire foot is missing (e.g. 5-foot iamb instead of 6-foot: `diff=-2` for `foot_size=2`) and **is rejected**.

**Default `allowed_mismatches=2`:** after filtering out pyrrhics and spondees, a line is considered **correct** if real (non-tolerated) mismatches ≤ 2 and the length is within bounds.

### Meter Accuracy metric

```
meter_accuracy = (lines with ok=True) / (total lines)
```

Computed per line. `1.0` = every line follows the metre.

---

## 9. Component 8 — Rhyme validator

**Files:** `src/infrastructure/validators/rhyme/phonetic_validator.py`, `src/infrastructure/validators/rhyme/pair_analyzer.py`, `src/infrastructure/validators/rhyme/scheme_extractor.py`
**Port:** `src/domain/ports/rhyme.py` → `IRhymeValidator`, `IRhymePairAnalyzer`, `IRhymeSchemeExtractor`
**Phonetics:** `src/infrastructure/phonetics/ukrainian_ipa_transcriber.py` → `IPhoneticTranscriber`
**Precision enum:** `src/domain/value_objects.py` → `RhymePrecision`

### Rhyme schemes

```python
"AABB" → pairs (0,1), (2,3)       # paired rhyme
"ABAB" → pairs (0,2), (1,3)       # alternate rhyme
"ABBA" → pairs (0,3), (1,2)       # enclosed rhyme
"AAAA" → all line pairs           # monorhyme
```

### Rhyme check algorithm

**Step 1 — Find the last word of each line.**

**Step 2 — Transcribe to IPA (International Phonetic Alphabet):**

```python
# src/infrastructure/phonetics/ukrainian_ipa_transcriber.py
class UkrainianIpaTranscriber(IPhoneticTranscriber):
    _UA_MAP = {"а":"a", "б":"b", "г":"ɦ", "ж":"ʒ", "и":"ɪ", "і":"i", ...}

    def transcribe(self, word: str) -> str:
        # character-by-character mapping via _UA_MAP
        # "зелений" → "zelenjɪj"
```

**Why IPA:** comparing Cyrillic spelling is unreliable — `"ь"` is not a sound, `"я"` → `"ja"` (two symbols). IPA is a **phonetic representation**, which makes rhyme scoring more faithful.

**Step 3 — Rhyme part from the stressed vowel to the end:**

```python
def rhyme_part_from_stress(word, stress_syllable_idx_0based) -> str:
    ipa = transcribe_ua(word)
    vpos = vowel_positions_in_ipa(ipa)          # vowel positions in the IPA string
    stress_pos = vpos[stress_syllable_idx_0based]
    return ipa[stress_pos:]                     # from the stressed vowel onward
```

**Example:**
```
"зелений" → IPA: "zelenjɪj"
IPA vowel positions: [1 (e), 5 (e), 7 (ɪ)]
Stress on the 2nd vowel (index=1) → position 5
rhyme_part = "ɪj"

"натхненні" → IPA: "natxnenjɪ"
Stress on the 2nd vowel → rhyme_part = "i"
```

**Step 4 — Normalised Levenshtein distance:**

```python
# src/infrastructure/text/levenshtein_similarity.py (implements IStringSimilarity)
# + src/shared/string_distance.py (core algorithms)
def normalized_similarity(a: str, b: str) -> float:
    d = levenshtein_distance(a, b)
    return 1.0 - d / max(len(a), len(b))
```

Levenshtein distance counts the minimum number of edits (insertions, deletions, substitutions) to transform `a` into `b`. Normalised similarity = `1 - d/max_len` ∈ [0, 1].

**Threshold:** the rhyme is considered **correct** when `score >= rhyme_threshold` (default `0.55`, configured via `ValidationConfig`).

### Rhyme precision classification (`RhymePrecision`)

**Enum:** `src/domain/value_objects.py` (`RhymePrecision`)
**Computed in:** `src/infrastructure/validators/rhyme/pair_analyzer.py` → `PhoneticRhymePairAnalyzer._classify(...)`

| Level | Description |
|-------|-------------|
| `EXACT` | full match from the stressed vowel to the end |
| `ASSONANCE` | vowels match, consonants diverge |
| `CONSONANCE` | consonants match, vowels diverge |
| `INEXACT` | partial similarity above threshold |
| `NONE` | score below threshold — no rhyme |

### Rhyme Accuracy metric

```
rhyme_accuracy = (pairs with rhyme_ok=True) / (total pairs)
```

For ABAB with 4 lines — 2 pairs: (0,2) and (1,3). If one pair rhymes — `0.5`.

---

## 10. Generation and regeneration cycle (Feedback Loop)

**Files:** `src/infrastructure/regeneration/feedback_cycle.py` (ValidationFeedbackCycle), `src/infrastructure/regeneration/feedback_iterator.py` (ValidatingFeedbackIterator), `src/infrastructure/regeneration/iteration_stop_policy.py` (MaxIterationsOrValidStopPolicy), `src/infrastructure/regeneration/line_index_merger.py` (LineIndexMerger)
**Ports:** `src/domain/ports/pipeline.py` → `IFeedbackCycle`, `IFeedbackIterator`, `IIterationStopPolicy`

### Step-by-step process

```
┌───────────────────────────────────────────────────────────────────────┐
│ DefaultPoemGenerationPipeline.build(GenerationRequest)                 │
│  (orchestrated by PoetryService.generate())                            │
└───────────────────────────────────────────────────────────────────────┘
         │
         ▼
[1] RetrievalStage                 → SemanticRetriever.retrieve(theme)
                                     top-5 semantically close poems
                                     (uses pre-computed LaBSE embeddings)
[2] MetricExamplesStage            → JsonMetricRepository.query(meter, feet, scheme)
                                     top-2 verified reference poems
                                     exact match on metre, feet, rhyme scheme
[3] PromptStage                    → RagPromptBuilder.build(state)
                                     assemble prompt with thematic + metric
                                     examples, stanza_count × lines_per_stanza
[4] GenerationStage                → ILLMProvider.generate(prompt) → Gemini writes
[5] ValidationStage                → CompositePoemValidator.validate(poem, meter, rhyme)
      IMeterValidator.validate()   → check each line per syllables/stress
                                     (with pyrrhics, spondees, catalexis)
      IRhymeValidator.validate()   → check line pairs for rhyme

[6] If meter_ok AND rhyme_ok       → ✅ DONE, return the poem

[7] FeedbackLoopStage (on violations):
    → ValidationFeedbackCycle.generate_feedback() for each line/pair
    → NumberedLinesRegenerationPromptBuilder.build() — prompt with errors
    → ILLMProvider.generate(regen_prompt) → Gemini fixes the lines
    → LineIndexMerger.merge(original, regenerated, feedback)
         ↑ safety guard: if LLM returned fewer lines — substitute original
    → CompositePoemValidator.validate() → re-validate merged poem
    → MaxIterationsOrValidStopPolicy — stop on valid OR max_iterations

[8] FinalMetricsStage (evaluation mode only):
    → MeterAccuracy, RhymeAccuracy, SemanticRelevance, IterationMetrics, LineCount

[9] Return the final poem + GenerationResult(poem, ValidationResult)
```

### Feedback message format

**Meter feedback:**
```
Line 2 violates ямб meter.
Expected stress on syllables: 2, 4, 6, 8.
Actual stress on syllables: 1, 2, 3, 5, 8.
Rewrite only this line, keep the meaning.
```

**Rhyme feedback:**
```
Lines 1 and 3 should rhyme (scheme ABAB).
Expected rhyme with ending 'ɪj'.
Current ending 'i' does not match (score: 0.00).
Rewrite line 3 keeping the meaning and meter.
```

**Why this detailed feedback:** the LLM cannot "feel" metre. But when told exactly **which stress position is wrong** and **what IPA rhyme ending is expected**, it has enough information for a targeted fix of one line without rewriting the whole poem.

### The `max_iterations` parameter

| Value | Behaviour |
|-------|-----------|
| `0` | generation only, no feedback loop |
| `1` (default) | one correction attempt |
| `3+` | several attempts, each a separate API call |

`max_iterations=1` is the default to limit API cost. For ablation studies it can be raised via `--max-iterations N`.

### What `GenerationResult` returns

```python
@dataclass(frozen=True)
class GenerationResult:
    poem: str                         # final poem text
    validation: ValidationResult      # metre + rhyme validation result

@dataclass(frozen=True)
class ValidationResult:
    meter: MeterResult                # ok, accuracy, feedback per line
    rhyme: RhymeResult                # ok, accuracy, feedback per pair
    iterations: int                   # feedback-loop iterations consumed

@dataclass(frozen=True)
class MeterResult:
    ok: bool                          # every line follows the metre
    accuracy: float                   # fraction of valid lines [0,1]
    feedback: tuple[LineFeedback, ...]  # per-line issues

@dataclass(frozen=True)
class RhymeResult:
    ok: bool                          # every pair rhymes correctly
    accuracy: float                   # fraction of valid pairs [0,1]
    feedback: tuple[PairFeedback, ...]  # per-pair issues
```

---

## 11. Quality metrics — formulas and rationale

**Files:** `src/infrastructure/metrics/` (meter_accuracy, rhyme_accuracy, semantic_relevance, regeneration_success, iteration_metrics, line_count, registry)

Every metric implements the `IMetricCalculator` port and registers with `DefaultMetricCalculatorRegistry`. `FinalMetricsStage` runs the whole registry at the end of the pipeline and populates `context.final_metrics` — keys exactly match `IMetricCalculator.name`.

**Composition.** `MetricsSubContainer` is itself a thin façade composing two focused sub-containers: `CalculatorRegistrySubContainer` (registry + calculators + final stage) and `ReportingSubContainer` (reporter, results writers, tracer factory, HTTP error mapper, evaluation aggregator). Each lives in its own module under `src/infrastructure/composition/` so a new metric or a new writer touches one focused file rather than the broader metrics container.

**Metric registry (8 calculators):**

| Key | Class | File | Value | Zero when |
|-----|-------|------|-------|-----------|
| `meter_accuracy` | `MeterAccuracyCalculator` | `meter_accuracy.py` | fraction of lines passing the metre validator | poem empty |
| `rhyme_accuracy` | `RhymeAccuracyCalculator` | `rhyme_accuracy.py` | fraction of pairs passing the phonetic check | no pairs |
| `semantic_relevance` | `SemanticRelevanceCalculator` | `semantic_relevance.py` | cosine(embed(theme), embed(poem_text)) | `EmbedderError` or empty text |
| `regeneration_success` | `RegenerationSuccessCalculator` | `regeneration_success.py` | avg accuracy delta (metre+rhyme) first → last iteration | iterations < 2 |
| `meter_improvement` | `MeterImprovementCalculator` | `iteration_metrics.py` | `final.meter_accuracy − initial.meter_accuracy` | iterations < 2 |
| `rhyme_improvement` | `RhymeImprovementCalculator` | `iteration_metrics.py` | `final.rhyme_accuracy − initial.rhyme_accuracy` | iterations < 2 |
| `feedback_iterations` | `FeedbackIterationsCalculator` | `iteration_metrics.py` | feedback-loop iterations (excludes initial validation) | always defined |
| `num_lines` | `LineCountCalculator` | `line_count.py` | non-empty line count in the final poem | empty poem |

### 11.1 Meter Accuracy

```
meter_accuracy = Σ(line_i.ok) / N_lines
```

Where `line_i.ok = True` if the count of **real** (non-tolerated) stress mismatches ≤ `allowed_mismatches=2` **and** the line length is permitted (`_line_length_ok`).

**Why the 2 threshold:** classical poetry allows **rhythmic variations**. Pyrrhics and spondees on function and monosyllabic words are not errors — they're filtered before counting. A strict rule `≤0 mismatches` would reject canonical lines from Shevchenko, Lesya Ukrainka, Kostenko.

### 11.2 Rhyme Accuracy

```
rhyme_accuracy = Σ(pair_i.rhyme_ok) / N_pairs
```

Where `pair_i.rhyme_ok = True` when `normalized_similarity(rhyme_part_1, rhyme_part_2) ≥ rhyme_threshold` (default `0.55`, configured via `ValidationConfig`).

**Why this threshold:** rhyme is not always exact (masculine/feminine etc.). The threshold accepts inexact rhymes and assonance but rejects substantial divergences. The exact value was chosen experimentally on Ukrainian material.

### 11.3 Semantic Relevance

```python
# src/infrastructure/metrics/semantic_relevance.py
semantic_relevance = cosine(embed(theme), embed(poem_text))
                   = dot(theme_vec, poem_vec) / (||theme_vec|| * ||poem_vec||)
```

Measures **how semantically close the final poem is to the requested theme**. Uses the same `IEmbedder` (`LaBSEEmbedder` in prod, `OfflineDeterministicEmbedder` in tests) as `SemanticRetriever` — this guarantees metrological consistency with the retrieval phase.

**Range:** `[-1, 1]` theoretically, practically `[0, 1]` (normalised LaBSE vectors in a semantically valid space rarely yield negative cosines).

**Values ≥ 0.6** — topically on-theme. **≥ 0.8** — highly relevant. **< 0.4** — the model "drifted" to a side topic (often because of a weak prompt or too few retrieval examples).

**Failure behaviour:**
- `EmbedderError` (LaBSE unavailable, offline fallback didn't rescue it) → returns `0.0` and emits a `warning` log line. Does **not** crash the pipeline — semantic relevance is not critical for "the poem was generated".
- Under `OFFLINE_EMBEDDER=true` the metric degrades to noise (a deterministic hash vector with no semantic content). In research mode this should be flagged in reports.

**Why:** independent of `meter_accuracy` / `rhyme_accuracy` — **formal correctness** ≠ **thematic fidelity**. A poem can hold iamb + ABAB perfectly yet write about potato chips instead of "spring in a forest".

### 11.4 Regeneration Success (delta accuracy)

```python
# src/infrastructure/metrics/regeneration_success.py
initial = iterations[0]        # iteration 0 (initial-generation result)
final   = iterations[-1]       # last iteration (after every feedback pass)
regeneration_success = ((final.meter_accuracy - initial.meter_accuracy)
                      + (final.rhyme_accuracy - initial.rhyme_accuracy)) / 2.0
```

**Range:** `[-1, 1]`. Negative values are returned **as-is** (not clamped) — degradation is intentional to surface in reports as a signal of prompt / model trouble.

- `+0.3` — the feedback loop lifted mean accuracy by 30%.
- `0.0` — nothing changed (either it was perfect from the start, or the feedback didn't help).
- `-0.2` — **the model made the poem worse** while trying to fix it — an alarm bell.

**Zero when `len(iterations) < 2`:** the feedback loop didn't run (either `max_iterations=0` or the poem was valid on the first try).

**Why:** separates **correction effectiveness** from raw quality. A system with baseline 50% + feedback 80% is better than one with baseline 75% without feedback.

### 11.5 Meter / Rhyme Improvement (separate deltas)

```python
# src/infrastructure/metrics/iteration_metrics.py
meter_improvement = final.meter_accuracy - initial.meter_accuracy
rhyme_improvement = final.rhyme_accuracy - initial.rhyme_accuracy
```

A decomposition of `regeneration_success` into two channels. Reveals **where** the feedback loop invested its correction: if `meter_improvement=+0.4` but `rhyme_improvement=-0.05`, the model fixed metre and **broke** rhyme — a signal to tune the prompt format so both properties stay in sync.

### 11.6 Feedback Iterations

```python
feedback_iterations = max(0, len(iterations) - 1)
```

Number of feedback-loop invocations (excluding the initial generation). `0` = the poem was valid on the first attempt; `1..max_iterations` = how many reworks were needed.

**Under ablation runs:** the median of this metric across the scenario matrix is an indirect difficulty or model-weakness signal.

### 11.7 Num Lines

```python
num_lines = Poem.from_text(poem_text).line_count
```

The number of non-empty lines in the **final** poem (post-sanitization). `Poem.from_text` filters lines through `_is_poem_line()` — dropping scansion stubs, empty, bulleted.

**Diagnostic value:** expected = `request.structure.total_lines`. A mismatch signals:
- the sanitizer dropped real lines as "garbage" (false positive) → edit the regex rules;
- the model produced fewer/more lines than requested → tune the prompt or raise `max_iterations`.

Not averaged — used as a per-run diagnostic.

---

## 12. Evaluation Harness and ablation configs

**Files:** `src/services/evaluation_service.py` (`EvaluationService`), `src/runners/evaluation_runner.py` (`EvaluationRunner`), `scripts/run_evaluation.py`
**Scenarios:** `src/infrastructure/evaluation/scenario_data.py`, `src/infrastructure/evaluation/scenario_registry.py`
**Aggregation:** `src/infrastructure/evaluation/aggregator.py` → `DefaultEvaluationAggregator`

### Ablation configs

| Config | Semantic RAG | Metric Examples | Validation | Feedback | Purpose |
|--------|-------------|-----------------|------------|----------|---------|
| **A** | ❌ | ❌ | ✅ | ❌ | Baseline: LLM + validator, no RAG, no feedback |
| **B** | ❌ | ❌ | ✅ | ✅ | LLM + Val + Feedback (no RAG) |
| **C** | ✅ | ❌ | ✅ | ✅ | Semantic RAG + Val + Feedback |
| **D** | ❌ | ✅ | ✅ | ✅ | Metric Examples + Val + Feedback |
| **E** | ✅ | ✅ | ✅ | ✅ | **Full system** (semantic + metric examples + val + feedback) |
| **F** | ✅ | ❌ | ✅ | ❌ | Semantic RAG + Val (no feedback) — pure RAG effect |
| **G** | ❌ | ✅ | ✅ | ❌ | Metric Examples + Val (no feedback) — pure metric-examples effect |
| **H** | ✅ | ✅ | ✅ | ❌ | Semantic + Metric Examples + Val (no feedback) — pure combined effect |

**Why ablations:** comparing configs pair-wise isolates each component's contribution:

| Comparison | Measures |
|------------|----------|
| `A → B` | impact of the feedback loop |
| `B → C` | impact of semantic RAG (thematic inspiration) |
| `B → D` | impact of metric examples (rhythm template) |
| `C → E` or `D → E` | impact of combining both retrieval types |
| `A → F` | pure semantic-RAG effect on the first draft (not masked by feedback) |
| `A → G` | pure metric-examples effect on the first draft |
| `A → H` | pure combined-enrichment effect on the first draft |

> **Why F/G/H exist:** when feedback is enabled in both arms of a comparison, the loop iteratively repairs the initial draft and the contribution of an enrichment stage (RAG / metric examples) gets masked — both configs converge on similar final quality. F/G/H mirror C/D/E with feedback OFF, so paired-Δ vs. A measures the *raw* effect of each enrichment on the first-attempt poem.

### Evaluation matrix

```python
run_evaluation_matrix(
    scenarios=[...],    # N scenarios
    configs=[...],      # M configs
)
# → N × M traces + summary tables
```

### Quick run (demo)

```bash
# Run N01 through the full system (E), verbose, save results
make demo

# Another scenario via demo
make demo SCENARIO=N03
```

Results save to `results/demo_N01_YYYYMMDD_HHMMSS.json` and `results/demo_N01_YYYYMMDD_HHMMSS.md`.

### Evaluation runs

```bash
# One scenario, full system, detailed output
make evaluate SCENARIO=N01 CONFIG=E VERBOSE=1

# All normal scenarios, config C (no RAG)
make evaluate CATEGORY=normal CONFIG=C

# All scenarios × all configs (18 × 8 = 144 runs)
make evaluate

# With a custom corpus and specific output path
CORPUS_PATH=my_corpus.json make evaluate OUTPUT=results/run1.json

# Override poem structure for every scenario
make evaluate STANZAS=3 LINES_PER_STANZA=6
```

By default results are saved to `results/eval_YYYYMMDD_HHMMSS.json`.

The `STANZAS` / `LINES_PER_STANZA` Makefile variables (or `--stanzas` / `--lines-per-stanza` CLI flags) are applied to every selected scenario via `dataclasses.replace()` — original scenario objects are not mutated.

### Makefile variables for evaluation

| Variable | Default | Description |
|----------|---------|-------------|
| `SCENARIO` | *(all)* | Scenario ID: `N01`–`N05`, `E01`–`E05`, `C01`–`C08` |
| `CONFIG` | *(all)* | Ablation config: `A`–`H` |
| `CATEGORY` | *(all)* | Filter: `normal`, `edge`, or `corner` |
| `VERBOSE` | *(off)* | `1` for full stage-by-stage traces |
| `OUTPUT` | `results/eval_TIMESTAMP.json` | JSON path (`.md` report written alongside automatically) |
| `STANZAS` | `2` | Override stanza count |
| `LINES_PER_STANZA` | `4` | Override lines per stanza |

---

## 13. Test scenarios

**File:** `src/domain/scenarios.py`

18 curated scenarios across three categories. Each scenario fixes its poem structure:

```python
@dataclass(frozen=True)
class EvaluationScenario:
    ...
    stanza_count: int = 1       # stanza count
    lines_per_stanza: int = 4   # lines per stanza

    @property
    def total_lines(self) -> int:
        return self.stanza_count * self.lines_per_stanza
```

These values flow automatically into `RagPromptBuilder.build()` and define the generation size for the LLM. Can be overridden via `--stanzas` / `--lines-per-stanza` or `STANZAS` / `LINES_PER_STANZA` in the Makefile.

### NORMAL (N01–N05) — typical requests

| ID | Theme | Metre | Rhyme | Stanzas × Lines | Purpose |
|----|-------|-------|-------|-----------------|---------|
| N01 | Spring in a forest | iamb, 4-foot | ABAB | 1×4 (4 lines) | most common form |
| N02 | Love | trochee, 4-foot | AABB | 1×4 (4 lines) | folk-song tradition |
| N03 | Homeland (Ukraine) | dactyl, 4-foot | ABBA | 1×4 (4 lines) | ternary metre with enclosing rhyme |
| N04 | Loneliness | amphibrach, 4-foot | ABAB | 2×4 (8 lines) | less common ternary metre |
| N05 | City at night | anapest, 4-foot | AABB | 2×4 (8 lines) | urban theme, anapestic rhythm |

### EDGE (E01–E05) — boundary but valid

| ID | Particular | What it tests |
|----|-----------|---------------|
| E01 | 2-foot iamb, AABB | minimal line length |
| E02 | 6-foot iamb (alexandrine), ABAB | maximum line length |
| E03 | 6-foot anapest, ABBA | rare metre + scheme combination |
| E04 | 5-foot amphibrach, AAAA (monorhyme) | strictest rhyme constraint |
| E05 | 5-foot dactyl, ABAB, abstract theme | retrieval without nearby vectors |

### CORNER (C01–C08) — adversarial inputs

| ID | Input | What it tests |
|----|-------|---------------|
| C01 | minimal theme `"тиша"` (trochee, 6-foot, ABAB) | graceful handling of minimal input |
| C02 | theme > 200 chars (iamb, 5-foot, ABAB) | long prompt |
| C03 | English theme (dactyl, 3-foot, ABAB) | cross-language retrieval |
| C04 | metre `"гекзаметр"` (4-foot, ABAB) — unknown metre | validator error (`expected_to_succeed=False`) |
| C05 | `foot_count=1` (anapest, ABAB) | extreme minimum line length |
| C06 | emoji + HTML in theme (amphibrach, 6-foot, AABB) | input sanitisation |
| C07 | Ukrainian + Russian mix (iamb, 4-foot, ABAB) | output language consistency |
| C08 | `foot_count=0` (trochee, ABAB) — degenerate | crash safety (`expected_to_succeed=False`) |

---

## 14. Pipeline tracing (PipelineTrace)

**Files:** `src/infrastructure/tracing/pipeline_tracer.py` (`PipelineTracer`), `src/infrastructure/tracing/null_tracer.py` (`NullTracer`), `src/infrastructure/tracing/stage_timer.py` (`StageTimer`)
**Domain model:** `src/domain/evaluation.py` (`PipelineTrace`, `EvaluationSummary`)
**Port:** `src/domain/ports/tracing.py` → `ITracer`, `ITracerFactory`

Every run inside the evaluation harness records a full `PipelineTrace`:

```python
PipelineTrace
├── scenario_id: str              # "N01"
├── config_label: str             # "D"
├── stages: list[StageRecord]     # one record per stage
│   ├── name                      # "retrieval", "prompt_construction", ...
│   ├── input_summary             # brief: "theme='весна', corpus_size=153"
│   ├── input_data                # FULL DATA: theme, parameters, or poem text
│   ├── output_summary            # brief: "retrieved 5 poems, top_sim=0.8234"
│   ├── output_data               # FULL DATA: retrieved texts, prompt, etc.
│   ├── metrics                   # {"num_retrieved": 5, "top_similarity": 0.8234}
│   ├── duration_sec              # stage duration
│   └── error                     # None or error string
├── iterations: list[IterationRecord]  # each feedback-loop iteration
│   ├── iteration: int            # 0 = initial, 1 = after first feedback
│   ├── poem_text                 # full poem text at this iteration
│   ├── meter_accuracy            # [0,1]
│   ├── rhyme_accuracy            # [0,1]
│   └── feedback                  # messages sent to the LLM
├── final_poem: str               # final poem
├── final_metrics: dict           # meter_accuracy, rhyme_accuracy, feedback_iterations, num_lines, ...
├── total_duration_sec: float
└── error: str | None
```

The trace serialises to JSON via `trace.to_dict()` and persists when `--output results/eval.json` is passed. Alongside the JSON, a `.md` report is auto-generated with a per-scenario config comparison table and the final poems from each setup (`format_markdown_report()` in `runner.py`).

---

## 15. Environment variables and settings

### Runtime (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Gemini API key (required for real generation) |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | Model name. Default — paid (~\$2/1M in, ~\$12/1M out), best quality. Alternatives: `gemini-2.5-pro`, `gemini-2.5-flash` (free tier, worse quality for poetry) |
| `GEMINI_TEMPERATURE` | `0.9` | `[0, 2]`. Lowering to `0.3` on reasoning models reduces CoT leakage |
| `GEMINI_MAX_TOKENS` | `8192` | Max output tokens. Must be ≥ 8192 on reasoning models (otherwise `<POEM>` never emitted) |
| `GEMINI_DISABLE_THINKING` | `false` | `true` → pass `ThinkingConfig(thinking_budget=0)`. Supported only by Gemini 2.5; Pro-preview returns 400 |
| `LLM_TIMEOUT_SEC` | `120` | Hard per-call timeout. 120 s for Pro; drop to 20 s for flash |
| `LLM_RETRY_MAX_ATTEMPTS` | `2` | Retry attempts on `LLMError`. Timeout retries are usually futile but cover 5xx / rate-limit |
| `LLM_PROVIDER` | `""` (auto) | Force provider: `gemini`, `mock`, or empty for auto-detect |
| `CORPUS_PATH` | `corpus/uk_theme_reference_corpus.json` | Theme corpus JSON path |
| `METRIC_EXAMPLES_PATH` | `corpus/uk_metric-rhyme_reference_corpus.json` | Metric corpus path |
| `LABSE_MODEL` | `sentence-transformers/LaBSE` | HuggingFace embedding model |
| `OFFLINE_EMBEDDER` | `false` | Use the deterministic offline embedder (tests) |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Debug mode |

**Heads up:** **do not write inline comments** in `.env` — docker-compose's `env_file` parser reads them as part of the value. Put every explanation on its own line before the variable. `AppConfig.from_env` has a defensive `_str()` helper that strips a trailing `# comment`, but avoid the pattern anyway.

Detailed reference for every knob, reasoning-model tuning, and a common-failure table: [`reliability_and_config.md`](./reliability_and_config.md) ([UA](../ua/reliability_and_config.md)).

### Corpus management (Makefile)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `data` | Directory with `.txt` poem files |
| `THEME_OUT` | `corpus/uk_theme_reference_corpus.json` | Theme corpus output |
| `MIN_COUNT` | `1` | Minimum poem count |
| `THEME_CORPUS` | `corpus/uk_theme_reference_corpus.json` | Path for `embed-theme-corpus` |
| `METRIC_OUT` | `corpus/uk_auto_metric_corpus.json` | Metric-rhyme corpus output |
| `SAMPLE_LINES` | *(all)* | Sample first N lines per poem |

Without `GEMINI_API_KEY` the system automatically uses `MockLLMProvider` — sufficient for running tests and verifying the pipeline structure.

---

## 16. Data flow diagram

```
THEME CORPUS (corpus/uk_theme_reference_corpus.json)     METRIC-RHYME CORPUS (corpus/uk_metric-rhyme_reference_corpus.json)
  poems + LaBSE embeddings [768-dim]                     poems annotated with metre/rhyme
        │                                                  │
        │ JsonThemeRepository                               │ JsonMetricRepository.find(meter, feet, scheme)
        ▼                                                  ▼
  ┌─────────────┐     encode(theme) via LaBSE    ┌─────────────┐
  │ SemanticRe- │ ◄──────────────────────────    │ MetricExam- │   USER INPUT
  │  triever    │  cosine_similarity → top_k      │  ples       │ ◄──── (theme, meter,
  └─────────────┘                                 └─────────────┘        rhyme_scheme,
        │ top_k RetrievalItem                           │                 foot_count,
        │ {poem_id, text, similarity}                   │ top_k           stanza_count,
        └──────────────────┬────────────────────────────┘                 lines_per_stanza)
                           ▼                                              │
                     ┌─────────────┐ ◄────────────────────────────────────┘
                     │ build_rag_  │  theme + metre + scheme + structure
                     │   prompt()  │  = two blocks: thematic + metric examples
                     └─────────────┘
                           │ prompt string (~600-2500 chars)
                           ▼
    ┌────────────── LLM DECORATOR STACK (outermost → innermost) ──────────────┐
    │                                                                          │
    │   LoggingLLMProvider (INFO/ERROR + duration_sec)                         │
    │     │                                                                    │
    │     ▼                                                                    │
    │   RetryingLLMProvider (exp. backoff on LLMError, up to retry_max_attempts)│
    │     │                                                                    │
    │     ▼                                                                    │
    │   TimeoutLLMProvider (hard deadline timeout_sec)                         │
    │     │                                                                    │
    │     ▼                                                                    │
    │   SanitizingLLMProvider (allowlist filter; empty → LLMError → retry)     │
    │     │                                ◄── record_sanitized()              │
    │     ▼                                                                    │
    │   ExtractingLLMProvider (extract <POEM>…</POEM>)                         │
    │     │                                ◄── record_raw()  record_extracted()│
    │     ▼                                                                    │
    │   GeminiProvider ──────► generate_content() ◄────── poem text (CoT+envelope)
    │                                                                          │
    └──────────────────────────────────────────────────────────────────────────┘
                           │ cleaned poem text
                           ▼
                     ┌─────────────┐     UkrainianStressDict (ukrainian-word-stress + Stanza)
                     │ PatternMe-  │ ──► per-line stress pattern comparison
                     │  terValid.  │     pyrrhic/spondee tolerance + catalectic/feminine
                     └─────────────┘     → MeterResult
                           │
                     ┌─────────────┐     UkrainianIpaTranscriber → IPA
                     │ PhoneticRhy │ ──► LevenshteinSimilarity → normalized distance
                     │  meValid.   │     → RhymeResult + precision (EXACT/ASSONANCE/…)
                     └─────────────┘
                           │
                           ├── ALL OK? ──────────────────► RETURN poem
                           │
                           │ violations → feedback messages (UkrainianFeedbackFormatter)
                           ▼
                     ┌─────────────┐
                     │ Regeneration│  the same 5-layer decorator stack
                     │ llm-call    │  generate → raw → extract → sanitize → LLMError→retry
                     └─────────────┘
                           │
                     ┌─────────────┐
                     │ LineIndex-  │ ── 3 strategies:
                     │   Merger    │    A) full poem (regen == original lines)
                     │             │    B) partial splice by violation_indices
                     │             │    C) safety fallback (regen = copy of original → no-op)
                     └─────────────┘
                           │
                           └── validate() → (repeat, max_iterations times)
                                       │
                                       ▼
                                RETURN GenerationResult(poem, ValidationResult)
```
