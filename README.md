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

### 1. Poetry Corpus

* Curated corpus of Ukrainian poetic texts
* Used for: semantic retrieval, LLM prompting, experimental evaluation
* Treated as a **static linguistic resource**, not training data

### 2. Semantic Theme Retrieval Module

* Uses pretrained multilingual sentence embedding (LaBSE, 768-dim)
* Converts textual theme description into vector representation
* Retrieves semantically similar poems from the corpus (cosine similarity)
* Purpose: improve thematic consistency without fine-tuning the LLM

### 3. Metric Examples Retrieval Module

* Rule-based lookup in `corpus/ukrainian_poetry_dataset.json`
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

## Repository Structure

```
poetry-generation-ua/
│
├── docker/                   # Container configuration
├── src/                      # Core system modules
│   ├── pipeline/             # End-to-end generation pipelines
│   ├── retrieval/
│   │   ├── corpus.py         # CorpusPoem loading
│   │   ├── retriever.py      # LaBSE semantic retrieval + RAG prompt builder
│   │   └── metric_examples.py  # Metric/rhyme example retrieval
│   ├── generation/           # LLM interface (Gemini + Mock)
│   ├── meter/                # Meter validation (stress + pattern matching)
│   ├── rhyme/                # Rhyme validation (IPA + Levenshtein)
│   ├── evaluation/           # Scenarios, ablation runner, metrics, tracing
│   └── utils/                # Text utilities, distance functions
│
├── corpus/
│   ├── uk_poetry_corpus.json          # 153 poems + pre-computed LaBSE embeddings
│   └── ukrainian_poetry_dataset.json  # Verified meter/rhyme examples by classical authors
├── data/                     # Raw poem source files (.txt)
├── scripts/                  # Entry-point scripts
├── tests/
│   ├── unit/                 # Unit tests (213 tests)
│   └── integration/          # Integration tests
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
* 204 unit tests + integration tests, all passing in Docker

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
* Saves results to `results/demo_N01_YYYYMMDD_HHMMSS.json`
* To try a different scenario: `make demo SCENARIO=N03`

This is the fastest way to see the complete pipeline in action with a real Gemini API key, or with `MockLLMClient` when no key is configured.

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

The project includes a ready-to-use corpus (`corpus/uk_poetry_corpus.json`, 153 poems) with **pre-computed LaBSE embeddings** — no runtime encoding overhead during retrieval.

If you need to rebuild or extend the corpus from raw `.txt` files under `data/`, three Makefile targets are available:

```bash
make build-corpus                        # build corpus only (no embeddings)
make embed-corpus                        # compute LaBSE embeddings for existing corpus
make build-corpus-with-embeddings        # build corpus AND compute embeddings in one step
```

#### Corpus variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `data` | Source directory with `.txt` poem files |
| `OUT` | `corpus/uk_poetry_corpus.json` | Output corpus JSON path |
| `MIN_COUNT` | `1` | Minimum number of poems required to succeed |
| `CORPUS` | `corpus/uk_poetry_corpus.json` | Path used by `embed-corpus` |

Examples:

```bash
make build-corpus DATA_DIR=data OUT=corpus/uk_poetry_corpus.json MIN_COUNT=1
make embed-corpus CORPUS=corpus/uk_poetry_corpus.json
make build-corpus-with-embeddings DATA_DIR=data MIN_COUNT=50
```

You can also call the scripts directly:

```bash
# Build corpus with embeddings in one command
python3 scripts/build_corpus_from_data_dir.py \
  --data-dir data \
  --out corpus/uk_poetry_corpus.json \
  --min-count 1 \
  --embed

# Compute embeddings separately (idempotent — skips poems that already have them)
python3 scripts/build_corpus_embeddings.py --corpus corpus/uk_poetry_corpus.json
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
| `OUTPUT` | `results/evaluation.json` | Path to save JSON results |
| `STANZAS` | `2` | Number of stanzas to generate (overrides per-scenario default) |
| `LINES_PER_STANZA` | `4` | Lines per stanza (overrides per-scenario default) |

Both `STANZAS` and `LINES_PER_STANZA` override the values defined in the scenario. Total lines generated = `STANZAS × LINES_PER_STANZA`. Each scenario also defines its own defaults (see `src/evaluation/scenarios.py`), which take effect when the variables are not set.

#### Poem Structure per Scenario

Each `EvaluationScenario` carries `stanza_count`, `lines_per_stanza`, and a computed `total_lines` property. The prompt sent to the LLM explicitly specifies the required structure, e.g.:

```
Structure: 2 stanzas of 4 lines each (8 lines total)
Generate a Ukrainian poem with exactly 8 lines.
```

#### Scenario Categories

* **Normal** (N01–N05) — typical requests: iamb+ABAB, trochee+AABB, amphibrach, dactyl
* **Edge** (E01–E05) — boundary conditions: 2-foot minimal, 6-foot alexandrine, monorhyme AAAA, abstract theme
* **Corner** (C01–C08) — adversarial inputs: empty theme, XSS injection, unsupported meter, mixed languages, zero feet

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
* **Summary table** — meter accuracy, rhyme accuracy, iterations, duration per scenario × config
* **Aggregates** — averages by config and by category
* **JSON export** — full traces with stage-by-stage records, iteration history, and metrics

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
| `GEMINI_MAX_OUTPUT_TOKENS` | `4096` | Max tokens per generation |
| `CORPUS_PATH` | `corpus/uk_poetry_corpus.json` | Path to the poetry corpus JSON |

Without `GEMINI_API_KEY`, the system falls back to `MockLLMClient` (deterministic stub), which is sufficient for running tests and verifying the pipeline structure.

---

## Notes on Reproducibility

* All experiments executed **inside containers**
* Dependencies are locked via Poetry
* Same commands produce **identical environments across machines**

This ensures **experimental results can be reliably reproduced**.

---