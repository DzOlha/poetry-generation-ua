# Automated Generation of Ukrainian Poetry

*with Formal Control of Meter and Rhyme*

---

## Overview

This project implements a **hybrid system for automated generation of Ukrainian poetry** with explicit control over poetic meter and rhyme schemes.

Modern large language models (LLMs) are capable of producing fluent and creative text, but they cannot reliably satisfy strict formal constraints, such as **syllable count, stress placement, meter, or rhyme** — especially in morphologically rich languages like Ukrainian.

This work addresses that limitation by **separating semantic generation from formal validation**, combining:

* **Neural models** for semantic relevance
* **LLM** for text generation
* **Rule-based linguistic modules** for formal verification of meter and rhyme

The system is designed as a **fully containerized, reproducible, and modular research prototype**, suitable for experimental evaluation and further extension.

---

## Research Goal

**Primary goal:**

Design and implement an automated system that generates Ukrainian poetry while explicitly controlling poetic meter and rhyme using **interpretable linguistic rules**, and experimentally evaluate the impact of such control compared to unconstrained LLM generation.

---

## Key Design Principles

1. **Separation of responsibilities**

   * Semantics → neural models
   * Text generation → LLM
   * Formal structure → rule-based linguistic analysis

2. **Interpretability**

   * All meter and rhyme decisions are **deterministic and explainable**

3. **Reproducibility**

   * Entire system runs inside Docker containers
   * No local dependencies are required

4. **Minimal use of deep learning**

   * Neural models are used only for **semantic similarity**
   * Formal poetic structure is **explicitly modeled**, not learned

---

## High-Level System Architecture

```
User Input (theme, meter, rhyme scheme, foot count)
                ↓
Semantic Theme Retrieval (LaBSE)      Metric Examples Retrieval (rule-based)
   finds thematically similar poems       finds verified verse with exact meter/rhyme
                ↓                                         ↓
                └─────────── RAG Prompt Construction ─────┘
                                      ↓
                             LLM Text Generation
                                      ↓
                    Rule-based Meter & Rhyme Validation
                                      ↓
                    Optional Feedback-Driven Regeneration
                                      ↓
                                 Final Poem
```

---

## System Components

### 1. Poetry Corpora

* **Theme reference corpus** (`uk_theme_reference_corpus.json`) — curated corpus of Ukrainian poems with LaBSE embeddings for semantic retrieval by theme
* **Metric-rhyme reference corpus** (`uk_metric-rhyme_reference_corpus.json`) — manually verified examples with exact meter, foot count, and rhyme scheme for rhythm/rhyme reference in prompts
* **Auto-detected metric corpus** (`uk_auto_metric_corpus.json`) — automatically classified poems via brute-force meter/rhyme detection (built from `data/`)
* Used for: semantic retrieval, metric examples retrieval, LLM prompting, experimental evaluation
* Treated as **static linguistic resources**, not training data

### 2. Semantic Theme Retrieval Module

* Uses pretrained multilingual sentence embedding (LaBSE, 768-dim)
* Converts textual theme description into vector representation
* Retrieves semantically similar poems from the corpus (cosine similarity)
* Purpose: improve thematic consistency without fine-tuning the LLM

### 3. Metric Examples Retrieval Module

* Rule-based lookup in `corpus/uk_metric-rhyme_reference_corpus.json`
* Finds verified example quatrains with exact meter, foot count, and rhyme scheme
* Covers all 5 meters × multiple foot counts × multiple rhyme schemes
* Verified examples (classical Ukrainian poets) are prioritized
* Purpose: give the LLM a rhythm and rhyme template to follow

### 4. LLM-based Generator

* Generates poetic text based on:

  * user-defined theme
  * semantically retrieved thematic examples
  * metrically correct verse examples as rhythm/rhyme reference
  * structural constraints (number of stanzas, lines per stanza)
* **Does not validate meter or rhyme**; produces candidate text

### 5. Meter Validation Module (Rule-Based)

* Deterministic module:

  * splits text into lines and words
  * performs syllabification using `ukrainian-word-stress` + Stanza NLP
  * assigns stress positions per word
  * compares stress pattern against metrical template (iamb, trochee, dactyl, amphibrach, anapest)
  * tolerates pyrrhic substitutions (unstressed at strong position) for function words and monosyllabic words
  * tolerates spondee substitutions (stressed at weak position) for monosyllabic words
  * accepts feminine (+1), dactylic (+2), and catalectic (−1 to −3) line endings
* Output: **pass/fail** + syllable-level mismatch positions

### 6. Rhyme Validation Module (Rule-Based)

* Analyzes line endings:

  * extracts phonetic endings
  * compares endings across lines
  * checks conformity to rhyme scheme (e.g., AABB, ABAB)
* Fully symbolic and language-specific

### 7. Feedback & Regeneration Loop

* If formal violations are detected:

  * generates structured feedback
  * performs controlled regeneration
  * logs results for experimental analysis

---

## Experimental Evaluation

Supports systematic experiments:

* Baseline comparison: **pure LLM generation without formal control**
* Ablation studies: disabling individual modules (retrieval, feedback)
* Automatic metrics: meter accuracy, rhyme accuracy, regeneration success rate
* Human evaluation: perceived poetic quality and thematic relevance

---

## Architecture

The system is structured around **Domain-Driven Design** with clear separation between domain logic, infrastructure adapters, and the application layer.

### Design Principles

| Principle | How it is applied |
|-----------|------------------|
| **Single Responsibility** | Each class has one reason to change: `PoetryService` orchestrates generation, `EvaluationService` runs ablation matrix, `RagPromptBuilder` builds prompts |
| **Open/Closed** | New meter validators, rhyme checkers, or retrievers are plugged in via interfaces — no pipeline changes required |
| **Dependency Inversion** | High-level services depend on abstract ports (`IThemeRepository`, `IRhymeValidator`, `IPromptBuilder`, …), not concrete classes |
| **Dependency Injection** | All dependencies are injected through constructors; `composition_root.py` wires production defaults via a centralized `Container` |
| **Strategy Pattern** | `IMeterValidator`, `IRhymeValidator`, `IPromptBuilder`, `IIterationStopPolicy` are interchangeable strategies |
| **Repository Pattern** | `IThemeRepository`, `IMetricRepository` hide storage details behind domain ports |
| **Decorator Pattern** | LLM reliability stack: `LoggingLLMProvider` → `RetryingLLMProvider` → `TimeoutLLMProvider` → real provider |
| **Composite Pattern** | `CompositeEmbedder` (primary + fallback), `CompositePoemValidator` (meter + rhyme) |
| **Null Object Pattern** | `NullTracer`, `NullLogger` — safe no-op implementations |
| **Contract Tests** | `IEmbedderContract`, `ILLMProviderContract`, `IMetricCalculatorContract` — behavioral guarantees for port implementations |
| **Registry Pattern** | `DefaultMetricCalculatorRegistry`, `ScenarioRegistry`, `DefaultLLMProviderFactory` — runtime registration of implementations |
| **Value Objects** | `GenerationRequest` replaces long argument lists; `MeterSpec`, `RhymeScheme`, `PoemStructure` are immutable frozen dataclasses |

### Domain Model

```
GenerationRequest (command)
  ├── theme: str
  ├── MeterSpec (value object)  ← meter name + foot count
  ├── RhymeScheme (value object) ← ABAB / AABB / …
  └── PoemStructure (value object) ← stanzas × lines

GenerationResult (result)
  ├── poem: str
  └── ValidationResult   ← meter_ok, rhyme_ok, accuracy, feedback
```

### Key Service Classes

```
PoetryService                ← main façade (services/poetry_service.py)
  └── depends on:
      ├── IPoemGenerationPipeline  ← staged pipeline (retrieval → generation → validation → feedback)
      ├── IPoemValidator           ← composite meter + rhyme checking
      └── IProviderInfo            ← LLM provider metadata

EvaluationService            ← ablation matrix runner (services/evaluation_service.py)
  └── depends on:
      ├── IPipeline               ← evaluation pipeline (stages)
      ├── ITracerFactory           ← creates per-run tracers
      ├── IScenarioRegistry        ← 18 curated scenarios
      └── AblationConfig[]         ← 5 ablation configurations

DetectionService             ← meter/rhyme auto-detection (services/detection_service.py)
  └── depends on:
      ├── IMeterDetector           ← brute-force meter classifier
      └── IRhymeDetector           ← brute-force rhyme classifier
```

## Repository Structure

```
poetry-generation-ua/
│
├── docker/                        # Container configuration (Dockerfile, docker-compose.yml, entrypoint.sh)
├── docs/                          # ADRs and design documents
├── src/
│   ├── composition_root.py        # Centralised DI — Container + build_* factories
│   ├── config.py                  # AppConfig (frozen dataclass, loaded from env)
│   │
│   ├── domain/                    # Domain layer (DDD) — zero infrastructure imports
│   │   ├── models/                # Value objects, commands, results, entities
│   │   │   ├── specifications.py  # MeterSpec, RhymeScheme, PoemStructure
│   │   │   ├── commands.py        # GenerationRequest, ValidationRequest
│   │   │   ├── results.py         # MeterResult, RhymeResult, ValidationResult, GenerationResult
│   │   │   ├── entities.py        # ThemeExcerpt, MetricExample, LineTokens
│   │   │   └── aggregates.py      # Poem
│   │   ├── ports/                 # Abstract interfaces (ABC) — 30+ focused ports
│   │   ├── values.py              # MeterName, RhymePattern, ScenarioCategory enums
│   │   ├── errors.py              # DomainError hierarchy
│   │   ├── evaluation.py          # AblationConfig, EvaluationSummary, PipelineTrace
│   │   ├── feedback.py            # LineFeedback, PairFeedback
│   │   ├── scenarios.py           # EvaluationScenario, ScenarioRegistry
│   │   └── pipeline_context.py    # PipelineState (mutable stage aggregate)
│   │
│   ├── services/                  # Application layer — thin orchestrators
│   │   ├── poetry_service.py      # PoetryService — generate + validate façade
│   │   └── evaluation_service.py  # EvaluationService — ablation matrix runner
│   │
│   ├── handlers/                  # Transport adapters
│   │   ├── api/                   # FastAPI REST endpoints
│   │   │   ├── app.py             # Application factory + lifespan + error handler
│   │   │   ├── dependencies.py    # Depends() providers from app.state
│   │   │   ├── schemas.py         # Pydantic request/response models
│   │   │   └── routers/           # poems.py, health.py, detection.py
│   │   ├── web/                   # Jinja2 HTML interface
│   │   │   ├── routes/            # index, generation, validation, detection, evaluation
│   │   │   ├── templates/         # Jinja2 HTML templates
│   │   │   └── static/            # CSS/JS assets
│   │   └── cli/                   # Click CLI adapter
│   │       └── main.py            # generate, validate, detect, evaluate commands
│   │
│   ├── runners/                   # IRunner implementations for scripts/CLI
│   │   ├── generate_runner.py     # GenerateRunner — single poem generation
│   │   ├── validate_runner.py     # ValidateRunner — meter/rhyme validation
│   │   ├── evaluation_runner.py   # EvaluationRunner — ablation matrix + reporting
│   │   ├── detect_runner.py       # DetectRunner — meter/rhyme auto-detection
│   │   ├── build_corpus_runner.py # BuildCorpusRunner — theme reference corpus from data/
│   │   ├── build_metric_corpus_runner.py  # BuildMetricCorpusRunner — auto-detected metric corpus
│   │   ├── build_embeddings_runner.py     # BuildEmbeddingsRunner — LaBSE embeddings
│   │   └── preload_resources_runner.py    # PreloadResourcesRunner — Stanza/LaBSE download
│   │
│   ├── infrastructure/            # Concrete adapter implementations
│   │   ├── composition/           # DI sub-containers (primitives, validation, generation, metrics, evaluation, detection)
│   │   ├── llm/                   # LLM providers (GeminiProvider, MockLLMProvider) + decorator stack
│   │   ├── validators/            # Meter (Pattern, BSP) + Rhyme (Phonetic) + CompositePoemValidator
│   │   ├── stress/                # UkrainianStressDict, SyllableCounter, PenultimateFallbackStressResolver
│   │   ├── embeddings/            # LaBSE + OfflineDeterministic + Composite embedders
│   │   ├── retrieval/             # SemanticRetriever (cosine similarity over LaBSE vectors)
│   │   ├── repositories/          # JsonThemeRepository, DemoThemeRepository, JsonMetricRepository
│   │   ├── stages/                # Pipeline stages (retrieval, metric examples, prompt, generation, validation, feedback, final metrics)
│   │   ├── pipeline/              # SequentialPipeline, PoemGenerationPipeline, StageFactory, SkipPolicy
│   │   ├── regeneration/          # ValidationFeedbackCycle, ValidatingFeedbackIterator, stop policies
│   │   ├── prompts/               # RagPromptBuilder, NumberedLinesRegenerationPromptBuilder
│   │   ├── metrics/               # Metric calculators (meter/rhyme accuracy, semantic relevance, …) + registry
│   │   ├── evaluation/            # ScenarioRegistry, DefaultEvaluationAggregator
│   │   ├── reporting/             # MarkdownReporter, JsonResultsWriter
│   │   ├── tracing/               # PipelineTracer, NullTracer, StageTimer
│   │   ├── text/                  # UkrainianTextProcessor, LevenshteinSimilarity
│   │   ├── phonetics/             # UkrainianIpaTranscriber
│   │   ├── feedback/              # UkrainianFeedbackFormatter
│   │   ├── http/                  # HttpErrorMapper
│   │   ├── logging/               # StdOutLogger, NullLogger
│   │   ├── serialization/         # Evaluation JSON serializers
│   │   ├── corpus/                # PoemFileParser
│   │   ├── detection/             # MeterDetector, RhymeDetector, StanzaSampler
│   │   └── meter/                 # MeterCanonicalizer, UkrainianMeterTemplates, WeakStressLexicon, SyllableFlagStrategy
│   │
│   └── shared/                    # Thin cross-cutting pure utilities
│       ├── string_distance.py     # Levenshtein distance / normalised similarity
│       └── text_utils_ua.py       # Ukrainian text helpers (vowel detection, syllable counting)
│
├── corpus/
│   ├── uk_theme_reference_corpus.json          # Theme corpus + LaBSE embeddings (153 poems, semantic retrieval)
│   ├── uk_metric-rhyme_reference_corpus.json   # Manually verified meter/rhyme reference examples (38 entries)
│   └── uk_auto_metric_corpus.json              # Auto-detected meter/rhyme corpus (built by build-metric-corpus)
├── data/                          # Raw poem source files (.txt)
├── docs/                          # ADRs and design documents
├── scripts/                       # Entry-point scripts (run_pipeline, run_evaluation, build_corpus_*, preload_stanza)
├── tests/
│   ├── contracts/                 # Shared interface contract base classes (IEmbedderContract, ILLMProviderContract, …)
│   ├── fixtures/                  # Layered fixtures (infrastructure, validators, services, domain)
│   ├── unit/                      # Mirrors src/ structure (~570 tests)
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── handlers/
│   │   ├── runners/
│   │   └── services/
│   └── integration/               # Full pipeline tests with real ML models (~51 tests)
│       ├── handlers/
│       └── services/
└── README.md
```

---

## Reproducibility & Deployment

* Entire system runs inside **Docker**
* No local Python installation required
* Experiments can be reproduced from a clean environment using a **single command**

---

## Academic Context

* Developed as part of a **Master’s thesis in Software Engineering**
* Focus areas:

  * hybrid AI system design
  * controlled natural language generation
  * symbolic vs. neural methods
  * reproducible experimental research

---

## Status

Fully implemented and tested:

* Complete RAG pipeline: semantic retrieval + metric examples retrieval + LLM generation
* Rule-based meter validator (5 meters, pyrrhic/spondee tolerance, feminine/catalectic endings)
* Rule-based rhyme validator (IPA transcription + Levenshtein distance)
* Feedback & regeneration loop
* Evaluation harness: 18 scenarios × 5 ablation configs (90 runs)
* 621 tests (570 unit + 51 integration), all passing in Docker

---

## Quick Start — OOP API

The preferred way to use the system programmatically is through `PoetryService`:

```python
from src.composition_root import build_poetry_service
from src.config import AppConfig
from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme

# Describe the poem to generate
request = GenerationRequest(
    theme="весна у лісі, пробудження природи",
    meter=MeterSpec(name="ямб", foot_count=4),
    rhyme=RhymeScheme(pattern="ABAB"),
    structure=PoemStructure(stanza_count=2, lines_per_stanza=4),
    max_iterations=3,
)

# Wire up the service (reads GEMINI_API_KEY from env, falls back to MockLLMProvider)
service = build_poetry_service(AppConfig.from_env())

# Generate
result = service.generate(request)
print(result.poem)
print(f"Meter OK: {result.validation.meter.ok}")
print(f"Rhyme OK: {result.validation.rhyme.ok}")
```

---

## Running the Project

All components run **inside Docker containers**; no local Python installation or system dependencies are required.

Project management and execution are handled via **Makefile**.

### Prerequisites

* Docker (version 20+)
* Docker Compose (v2)
* GNU Make

---

### Development Environment Setup

```bash
make up
```

* Builds Docker images
* Starts required services in detached mode
* Prepares an isolated development environment

---

### Accessing the Container

```bash
make bash
```

* Opens an interactive shell in the container
* Poetry virtualenv activated
* Useful for running exploratory scripts, inspecting intermediate data, and manual debugging

---

### Quick Demo — Run the Full System

```bash
make demo
```

* Runs scenario **N01** (весна у лісі, ямб 4ст, ABAB) through the **full system** (config E)
* Prints a stage-by-stage trace: retrieval → metric examples → prompt → generation → validation → feedback
* Saves results to `results/demo_N01_YYYYMMDD_HHMMSS.json` and a human-readable `results/demo_N01_YYYYMMDD_HHMMSS.md`
* To try a different scenario: `make demo SCENARIO=N03`

This is the fastest way to see the complete pipeline in action with a real Gemini API key, or with `MockLLMProvider` when no key is configured.

---

### Running the Generation Pipeline

```bash
make pipeline
```

* Executes the full poetry generation pipeline
* Uses Poetry-managed Python environment
* Output stored in container-mounted volumes for reproducibility

---

### Running Tests

```bash
make test                # all tests (unit + integration)
make test-unit           # only unit tests
make test-integration    # only integration tests
```

* Automatically pre-downloads Stanza and LaBSE models before running tests
* Models are cached in Docker volumes — subsequent runs start instantly

---

## Corpus Management

The project uses two separate corpora, both built from raw `.txt` files under `data/`:

| Corpus | File | Purpose |
|--------|------|---------|
| **Theme reference** | `corpus/uk_theme_reference_corpus.json` | Poems + LaBSE embeddings for semantic retrieval by theme |
| **Metric-rhyme reference** | `corpus/uk_metric-rhyme_reference_corpus.json` | Manually verified examples with exact meter, foot count, and rhyme scheme |
| **Auto-detected metric** | `corpus/uk_auto_metric_corpus.json` | Auto-detected meter/rhyme via brute-force detection (built by `build-metric-corpus`) |

### Theme Reference Corpus

Ready-to-use corpus with **pre-computed LaBSE embeddings** — no runtime encoding overhead during retrieval.

```bash
make build-theme-corpus                        # build corpus only (no embeddings)
make embed-theme-corpus                        # compute LaBSE embeddings for existing corpus
make build-theme-corpus-with-embeddings        # build corpus AND compute embeddings in one step
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `data` | Source directory with `.txt` poem files |
| `THEME_OUT` | `corpus/uk_theme_reference_corpus.json` | Output corpus JSON path |
| `MIN_COUNT` | `1` | Minimum number of poems required to succeed |
| `THEME_CORPUS` | `corpus/uk_theme_reference_corpus.json` | Path used by `embed-theme-corpus` |

Examples:

```bash
make build-theme-corpus DATA_DIR=data THEME_OUT=corpus/uk_theme_reference_corpus.json MIN_COUNT=1
make embed-theme-corpus THEME_CORPUS=corpus/uk_theme_reference_corpus.json
make build-theme-corpus-with-embeddings DATA_DIR=data MIN_COUNT=50
```

### Metric-Rhyme Corpus (auto-detected)

Scans poems in `data/`, runs brute-force meter and rhyme detection, and writes qualifying poems to a JSON corpus file.

```bash
make build-metric-corpus                                    # default output
make build-metric-corpus DATA_DIR=data METRIC_OUT=corpus/uk_auto_metric_corpus.json
make build-metric-corpus SAMPLE_LINES=8                     # sample first N lines per poem
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `data` | Source directory with `.txt` poem files |
| `METRIC_OUT` | `corpus/uk_auto_metric_corpus.json` | Output JSON path |
| `SAMPLE_LINES` | *(all)* | Number of leading lines to sample per poem |

### Direct script usage

```bash
# Build theme corpus with embeddings in one command
python3 scripts/build_corpus_from_data_dir.py \
  --data-dir data \
  --out corpus/uk_theme_reference_corpus.json \
  --min-count 1 \
  --embed

# Compute embeddings separately (idempotent — skips poems that already have them)
python3 scripts/build_corpus_embeddings.py --corpus corpus/uk_theme_reference_corpus.json

# Build auto-detected metric-rhyme corpus
python3 scripts/build_metric_corpus.py --data-dir data --out corpus/uk_auto_metric_corpus.json
```

The corpus path can also be set at runtime via the `CORPUS_PATH` environment variable:

```bash
CORPUS_PATH=corpus/my_corpus.json make evaluate SCENARIO=N01 CONFIG=D
```

---

### Evaluation Harness

Run the automated evaluation pipeline with **18 curated scenarios × 5 ablation configs**.

```bash
make evaluate                                        # all scenarios × all configs (90 runs)
make evaluate SCENARIO=N01                           # one scenario, all configs
make evaluate SCENARIO=N01 CONFIG=E                  # one scenario, full system (~1–4 API calls)
make evaluate CONFIG=E                               # all scenarios, full system config
make evaluate CATEGORY=corner                        # only corner-case scenarios
make evaluate SCENARIO=N01 CONFIG=E VERBOSE=1        # with detailed stage-by-stage traces
make evaluate OUTPUT=results/my_run.json             # custom output path
make evaluate STANZAS=2 LINES_PER_STANZA=4           # override poem structure for all scenarios
make evaluate SCENARIO=N01 STANZAS=3 LINES_PER_STANZA=6  # specific scenario, custom structure
```

#### Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCENARIO` | *(all)* | Scenario ID: `N01`–`N05`, `E01`–`E05`, `C01`–`C08` |
| `CONFIG` | *(all)* | Ablation config: `A`, `B`, `C`, `D`, or `E` |
| `CATEGORY` | *(all)* | Filter by category: `normal`, `edge`, or `corner` |
| `VERBOSE` | *(off)* | Set to `1` for full stage-by-stage traces |
| `OUTPUT` | `results/eval_TIMESTAMP.json` | Path to save JSON results (`.md` report is written alongside automatically) |
| `STANZAS` | `2` | Number of stanzas to generate (overrides per-scenario default) |
| `LINES_PER_STANZA` | `4` | Lines per stanza (overrides per-scenario default) |

Both `STANZAS` and `LINES_PER_STANZA` override the values defined in the scenario. Total lines generated = `STANZAS × LINES_PER_STANZA`. Each scenario also defines its own defaults (see `src/domain/scenarios.py`), which take effect when the variables are not set.

#### Poem Structure per Scenario

Each `EvaluationScenario` carries `stanza_count`, `lines_per_stanza`, and a computed `total_lines` property. The prompt sent to the LLM explicitly specifies the required structure, e.g.:

```
Structure: 2 stanzas of 4 lines each (8 lines total)
Generate a Ukrainian poem with exactly 8 lines.
```

#### Scenario Categories

* **Normal** (N01–N05) — typical requests: iamb+ABAB, trochee+AABB, amphibrach, dactyl
* **Edge** (E01–E05) — boundary conditions: 2-foot minimal, 6-foot alexandrine, monorhyme AAAA, abstract theme
* **Corner** (C01–C08) — adversarial inputs: minimal theme, XSS injection, unsupported meter, mixed languages, zero feet

#### Ablation Configs

| Config | Semantic RAG | Metric Examples | Validator | Feedback | Description |
|--------|-------------|-----------------|-----------|----------|-------------|
| **A** | ✗ | ✗ | ✓ | ✗ | Baseline (LLM + validator, no RAG, no feedback) |
| **B** | ✗ | ✗ | ✓ | ✓ | LLM + Val + Feedback (no RAG) |
| **C** | ✓ | ✗ | ✓ | ✓ | Semantic RAG + Val + Feedback |
| **D** | ✗ | ✓ | ✓ | ✓ | Metric Examples + Val + Feedback |
| **E** | ✓ | ✓ | ✓ | ✓ | Full system (semantic + metric examples + val + feedback) |

Comparing pairs measures each component's contribution: `A→B` = impact of feedback loop, `B→C` = impact of semantic retrieval (thematic RAG), `B→D` = impact of metric examples retrieval (rhythm/rhyme RAG), `C→E` or `D→E` = impact of combining both retrieval types.

#### Output

Each run produces:
* **Summary table** — meter accuracy, rhyme accuracy, iterations, duration per scenario × config (printed to terminal)
* **Aggregates** — averages by config and by category (printed to terminal)
* **JSON export** — full traces with stage-by-stage records, iteration history, and metrics (`results/eval_TIMESTAMP.json`)
* **Markdown report** — human-readable comparison table per scenario + final poem for each config (`results/eval_TIMESTAMP.md`), written automatically alongside the JSON

> **Tip:** For a quick test with real Gemini, run:
> `make evaluate SCENARIO=N01 CONFIG=E VERBOSE=1`
> This runs the full system (semantic + metric examples + validation + feedback) with ~1–4 API calls and shows the complete pipeline trace.

---

### Stopping and Cleaning Up

```bash
make down
```

* Stops all containers
* Removes volumes and orphaned resources
* Recommended when switching branches, resetting experiments, or reclaiming disk space

---

### Rebuilding Images

```bash
make rebuild
```

* Rebuilds Docker images from scratch without cache
* Useful when dependency definitions or Dockerfiles change

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Google Gemini API key (required for real LLM) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `GEMINI_TEMPERATURE` | `0.9` | Sampling temperature |
| `GEMINI_MAX_TOKENS` | `4096` | Max tokens per generation |
| `LLM_PROVIDER` | (auto) | Force provider: `gemini`, `mock`, or empty for auto-detect |
| `CORPUS_PATH` | `corpus/uk_theme_reference_corpus.json` | Path to the theme poetry corpus JSON |
| `METRIC_EXAMPLES_PATH` | `corpus/uk_metric-rhyme_reference_corpus.json` | Path to metric/rhyme reference corpus |
| `LABSE_MODEL` | `sentence-transformers/LaBSE` | HuggingFace model for semantic embeddings |
| `OFFLINE_EMBEDDER` | `false` | Use deterministic offline embedder (for tests) |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8000` | Server bind port |
| `DEBUG` | `false` | Enable debug mode |

Without `GEMINI_API_KEY`, the system falls back to `MockLLMProvider` (deterministic stub), which is sufficient for running tests and verifying the pipeline structure.

---

## Notes on Reproducibility

* All experiments executed **inside containers**
* Dependencies are locked via Poetry
* Same commands produce **identical environments across machines**

This ensures **experimental results can be reliably reproduced**.

---