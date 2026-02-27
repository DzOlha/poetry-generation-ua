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
User Input (theme, meter, rhyme scheme)
                ↓
Theme Embedding & Retrieval (DL)
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

### 2. Theme Embedding & Retrieval Module

* Uses pretrained multilingual sentence embedding (e.g., LaBSE)
* Converts textual theme description into vector representation
* Retrieves semantically similar poems from the corpus
* Purpose: improve thematic consistency without fine-tuning the LLM

### 3. LLM-based Generator

* Generates poetic text based on:

  * user-defined theme
  * retrieved poetic examples
  * soft structural hints (number of lines, style)
* **Does not validate meter or rhyme**; produces candidate text

### 4. Meter Validation Module (Rule-Based)

* Deterministic module:

  * splits text into lines and words
  * performs syllabification
  * assigns stress positions
  * compares stress pattern with metrical template (e.g., iamb, trochee)
* Output: **pass/fail** + detailed explanation of violations

### 5. Rhyme Validation Module (Rule-Based)

* Analyzes line endings:

  * extracts phonetic endings
  * compares endings across lines
  * checks conformity to rhyme scheme (e.g., AABB, ABAB)
* Fully symbolic and language-specific

### 6. Feedback & Regeneration Loop

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
├── docker/          # Container configuration
├── src/             # Core system modules
│   ├── pipeline/    # End-to-end generation pipelines
│   ├── retrieval/   # Semantic retrieval logic
│   ├── generation/  # LLM interface
│   ├── meter/       # Meter validation
│   ├── rhyme/       # Rhyme validation
│
├── corpus/          # Poetry corpus
├── data/            # Intermediate data
├── experiments/     # Experimental configurations
├── evaluation/      # Metrics and analysis
├── scripts/         # Entry-point scripts
├── tests/           # Unit tests
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

Currently provides:

* Architectural skeleton
* Containerized environment
* Baseline pipeline structure

**Modules will be implemented and evaluated incrementally**

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
* Useful for:

  * running exploratory scripts
  * inspecting intermediate data
  * manual debugging

---

### Running the Generation Pipeline

```bash
make pipeline
```

* Executes the full poetry generation pipeline
* Uses Poetry-managed Python environment
* Output stored in container-mounted volumes for reproducibility

---

## Building a Poetry Corpus (for RAG)

The project includes a script that builds a corpus from local poem files stored under the repository `data/` directory, cleans them, and saves a JSON corpus ready for the retrieval module.

```bash
python3 scripts/build_corpus_from_data_dir.py --data-dir data --out corpus/uk_poetry_corpus.json --min-count 44
```

Optional parameters:

```bash
python3 scripts/build_corpus_from_data_dir.py \
  --data-dir data \
  --min-count 500 \
  --out corpus/uk_poetry_corpus.json
```

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

### Evaluation Harness

Run the automated evaluation pipeline with **18 curated scenarios × 5 ablation configs**.

```bash
make evaluate                                   # all scenarios × all configs (90 runs)
make evaluate SCENARIO=N01                      # one scenario, all configs
make evaluate SCENARIO=N01 CONFIG=D             # one scenario, one config (~1-4 API calls)
make evaluate CONFIG=D                          # all scenarios, one config
make evaluate CATEGORY=corner                   # only corner-case scenarios
make evaluate SCENARIO=N01 CONFIG=D VERBOSE=1   # with detailed stage-by-stage traces
make evaluate OUTPUT=results/my_run.json        # custom output path
```

#### Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCENARIO` | *(all)* | Scenario ID: `N01`–`N05`, `E01`–`E05`, `C01`–`C08` |
| `CONFIG` | *(all)* | Ablation config: `A`, `B`, `C`, `D`, or `E` |
| `CATEGORY` | *(all)* | Filter by category: `normal`, `edge`, or `corner` |
| `VERBOSE` | *(off)* | Set to `1` for full stage-by-stage traces |
| `OUTPUT` | `results/evaluation.json` | Path to save JSON results |

#### Scenario Categories

* **Normal** (N01–N05) — typical requests: iamb+ABAB, trochee+AABB, amphibrach, dactyl
* **Edge** (E01–E05) — boundary conditions: 2-foot minimal, 6-foot alexandrine, monorhyme AAAA, abstract theme
* **Corner** (C01–C08) — adversarial inputs: empty theme, XSS injection, unsupported meter, mixed languages, zero feet

#### Ablation Configs (from spec §9)

| Config | Retrieval | Validator | Feedback | Description |
|--------|-----------|-----------|----------|-------------|
| **A** | ✗ | ✗ | ✗ | Baseline (pure LLM) |
| **B** | ✗ | ✓ | ✗ | LLM + Validator |
| **C** | ✗ | ✓ | ✓ | LLM + Val + Feedback |
| **D** | ✓ | ✓ | ✓ | Full system |
| **E** | ✗ | ✓ | ✓ | No Retrieval |

#### Output

Each run produces:
* **Summary table** — meter accuracy, rhyme accuracy, BLEU, ROUGE-L per scenario×config
* **Aggregates** — averages by config and by category
* **JSON export** — full traces with stage-by-stage records, iteration history, and metrics

> **Tip:** For a quick test with real Gemini, run:
> `make evaluate SCENARIO=N01 CONFIG=D VERBOSE=1`
> This uses ~1–4 API calls and shows the complete pipeline trace.

---

### Stopping and Cleaning Up

```bash
make down
```

* Stops all containers
* Removes volumes and orphaned resources
* Recommended for:

  * switching branches
  * resetting experiments
  * reclaiming disk space

---

### Rebuilding Images

```bash
make rebuild
```

* Rebuilds Docker images from scratch
* Useful when:

  * dependency definitions change
  * Dockerfiles are modified
  * eliminating inconsistent states

---

## Notes on Reproducibility

* All experiments executed **inside containers**
* Dependencies are locked via Poetry
* Same commands produce **identical environments across machines**

This ensures **experimental results can be reliably reproduced**.

---