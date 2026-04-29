<p align="right">
  <strong>🇬🇧 English</strong> · <a href="./README.ua.md">🇺🇦 Українська</a>
</p>

# Ukrainian Poetry Generator

> Generate, validate, and analyse Ukrainian classical poetry — with an LLM handling the words and rule-based linguistics enforcing the meter and rhyme.

<p align="center">
  <a href="./docs/en/user_guide.md">
    <img src="./docs/img/homepage_hero.png" alt="Ukrainian Poetry Generator — landing page with the four tools: generate, validate, detect, advanced configurations" width="820">
  </a>
  <br>
  <em>Four tools, one page — click through to the <a href="./docs/en/user_guide.md">user guide</a>.</em>
</p>

[![tests](https://img.shields.io/badge/tests-1131%20passing-brightgreen)]() [![coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)]() [![python](https://img.shields.io/badge/python-3.13-blue)]() [![docker](https://img.shields.io/badge/runs%20in-Docker-2496ED)]()

```text
Theme: «весна у лісі, пробудження природи»
Meter: ямб, 4 стопи · Rhyme: ABAB · Stanzas: 1

→ Весна прийшла у ліс зелений,
  Де тінь і світло гомонить.
  Мов сни, пливуть думки натхненні,
  І серце в тиші стукотить.

✓ meter 100% · ✓ rhyme 100% · 2 LLM attempts · \$0.02
```

A web tool, JSON API, and research harness in one — built as a clean-architecture, fully reproducible Python project, designed as an MSc / research-grade prototype.

---

## Why this exists

Large language models write fluent Ukrainian but **routinely miss the formal constraints** of classical poetry: wrong stress placement, off-by-one syllable count, suffix-only «pseudo-rhymes». They cannot self-correct because they have no internal model of meter or rhyme.

This project **separates concerns**: the LLM generates the words; **rule-based linguistic modules** validate **meter** by comparing the actual stress pattern (resolved via a Ukrainian stress dictionary) against the expected foot template, and validate **rhyme** by transcribing line endings into IPA and computing phonetic similarity (Levenshtein on the rhyme part from the stressed vowel onward). When validation fails, structured feedback is fed back to the LLM for targeted regeneration.

The pipeline is **transparent and measurable**: every stage emits a trace, every metric is named, and an ablation harness quantifies what each component (semantic RAG, metric-rhyme few-shot examples, feedback loop) actually contributes.

---

## System requirements

Everything runs inside Docker, so you don't need Python / Stanza / sentence-transformers locally — Docker takes care of dependencies. But your host machine still needs the headroom for the containers.

### Software prerequisites

- **Docker** 20+ — Docker Desktop on macOS / Windows; native engine on Linux
- **Docker Compose** v2 (bundled with Docker Desktop)
- **GNU Make** (pre-installed on macOS / Linux; `choco install make` on Windows)
- **Git** — to clone the repo
- **(Windows)** WSL2 **or** Hyper-V enabled — Docker Desktop needs one of the two backends; native Windows containers are not supported. WSL2 is the modern default; Hyper-V works as a fallback (e.g. on Windows 10 Pro without WSL2)

### Hardware (recommended for full system)

| Resource | Minimum (mock LLM only) | Recommended (with LaBSE + real LLM) |
|----------|--------------------------|----------------------------------------|
| **CPU** | any 64-bit, 2+ cores | 4+ cores |
| **RAM (free)** | 4 GB | **8 GB** (LaBSE inference uses ~2-3 GB during runtime) |
| **Disk (free)** | 5 GB | **15 GB** (Docker images ~5 GB + LaBSE ~1.8 GB + Stanza ~500 MB + cache + corpus headroom) |
| **GPU** | not required | not required (CPU is fine for low-volume LaBSE inference; Gemini runs server-side) |
| **Network** | for initial Docker pulls only | + outbound HTTPS to Google for every Gemini call |
| **OS** | macOS 11+ / Linux (kernel 4.x+) / Windows 10/11 + WSL2 or Hyper-V | same |

> **First-time setup** downloads LaBSE (~1.8 GB) and Stanza (~500 MB) into a Docker volume. Plan ~5-15 minutes on a typical home connection. After that, models are cached and subsequent runs start instantly.

---

## Try it in 60 seconds

<details>
<summary><strong>Option A — full system with real Gemini (recommended)</strong></summary>

```bash
git clone https://github.com/DzOlha/poetry-generation-ua.git
cd poetry-generation-ua
cp .env.example .env
# edit .env and put your Gemini API key into GEMINI_API_KEY
make serve
```

Open http://localhost:8000.

**Getting a Gemini API key (one-time, 5 minutes):**

1. Go to **<https://aistudio.google.com/apikey>** → sign in with Google.
2. Click **«Create API key»** → copy the key.
3. The default model used by this project is **`gemini-3.1-pro-preview`** — it gives the best results for Ukrainian poetry, but it's a **paid** model. To use it you need to enable billing:
   - Go to **<https://aistudio.google.com/billing>**.
   - Click **«Set up billing»** → link a payment method (credit card).
   - That means real money on your card: to upgrade from the free tier to paid Tier 1 (where `gemini-3.1-pro-preview` lives), Google requires a first payment — in practice around **\$30** (a one-off charge that activates billing). The **\$300 Google Cloud free trial credit** offered to new Cloud accounts **does not apply to the Gemini API** — it only covers other Cloud services (Compute Engine, BigQuery, etc.). So plan to actually pay for every Gemini call out of pocket.
4. Paste the key into `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-3.1-pro-preview
   ```
5. Approximate pricing (verify on **<https://ai.google.dev/pricing>** — it changes):
   - **gemini-3.1-pro-preview** (default): \$2 / 1M input tokens, \$12 / 1M output tokens. A typical 1-stanza poem with 1 feedback iteration costs **~\$0.04**.
   - **gemini-2.5-pro**: \$1.25 / 1M input, \$10 / 1M output. Slightly cheaper, slightly worse quality.
   - **gemini-2.5-flash** (free tier available): **Significantly worse quality** for strict poetic structure — only use it for smoke-testing the pipeline, not for real generation. Set `GEMINI_MODEL=gemini-2.5-flash` to use.
6. **If you change `GEMINI_MODEL`, also update the price env vars** so the displayed cost (`~\$0.04` next to each generated poem, ablation totals, etc.) reflects reality — the calculator just multiplies token counts by these numbers, it doesn't know which model you picked:
   ```
   GEMINI_INPUT_PRICE_PER_M=2.0       # default matches gemini-3.1-pro-preview
   GEMINI_OUTPUT_PRICE_PER_M=12.0
   ```
   Reference values per 1M tokens (input / output): `gemini-3.1-pro-preview` 2.00 / 12.00 · `gemini-2.5-pro` 1.25 / 10.00 · `gemini-2.0-flash` 0.10 / 0.40. For other / newer models check **<https://ai.google.dev/pricing>**.

</details>

<details>
<summary><strong>Option B — explore without paying anything</strong></summary>

```bash
git clone https://github.com/DzOlha/poetry-generation-ua.git
cd poetry-generation-ua
make serve   # no .env needed
```

Open http://localhost:8000. Generation is disabled (form blocked with notice), but **validation, detection, and analytics work fully** — useful for exploring the architecture and the rule-based linguistic modules.

</details>

---

## What the web UI exposes

Open http://localhost:8000 — you'll see **four tools**, each on its own page:

| Page | What it does | Needs API key? |
|------|---------------|-----------------|
| 🪶 **Generation** | "Give me a poem on theme X with meter Y and rhyme scheme Z" | yes |
| ✓ **Validation** | "Check this poem against meter Y and scheme Z; show me where it breaks" | no |
| 🔍 **Detection** | "What meter and rhyme scheme does this poem use?" | no |
| ⚙️ **Advanced configurations** | Run preset scenarios through ablation configs A–H, full pipeline trace | yes |
| 📊 **Quality analytics** | Research dashboard with paired-Δ contributions, CIs, plots | no (reads pre-computed reports) |

---

## How it works (one diagram)

```
User: theme + meter + rhyme + stanza count
                ↓
   ┌────────────────────────────┐  ┌────────────────────────────┐
   │  Semantic RAG  (LaBSE)     │  │  Metric examples retrieval │
   │  thematically-similar      │  │  verified verses with the  │
   │  poems from corpus         │  │  exact meter+rhyme pattern │
   └─────────────┬──────────────┘  └──────────────┬─────────────┘
                 └──────── RAG prompt ─────────────┘
                                ↓
                       LLM generation (Gemini)
                                ↓
              ┌──────────────────────────────────────┐
              │  Rule-based validation               │
              │  • Meter:  actual stress pattern     │
              │            vs expected foot template │
              │  • Rhyme:  IPA transcription of line │
              │            endings + Levenshtein on  │
              │            the rhyme part            │
              └─────────────┬────────────────────────┘
                            ↓
                    fail? → structured feedback
                            ↓
                    LLM regeneration (up to 3×)
                            ↓
                       final poem + metrics
```

LLMs handle **content**; rule-based modules handle **form**. Validation is deterministic and explainable: for every "broken" verdict, the system can name the exact reason — the numbered syllable positions that should be stressed vs the ones that actually are (e.g. *expected: 2, 4, 6, 8 / actual: 1, 4, 6, 8*); the IPA suffix of the rhyme partner vs the IPA suffix of the offending line; and the numeric rhyme-similarity score that fell below the threshold (e.g. *score: 0.42*).

---

## Tech stack

- **Backend**: Python 3.13 · FastAPI · Pydantic · Poetry · Jinja2
- **LLM**: Google Gemini (configurable model: 2.0-flash, 2.5-pro, 3.x-pro)
- **Linguistics**:
  - Meter — `ukrainian-word-stress` (Stanza-backed) for stress resolution + custom Pattern algorithm for foot-template matching
  - Rhyme — custom Ukrainian → IPA transcriber + Levenshtein on the rhyme part (from the stressed vowel onward) + classifier (exact / assonance / consonance / inexact / none)
- **RAG**: LaBSE multilingual sentence embeddings (`sentence-transformers`)
- **Reliability**: typed retry / timeout / sanitization decorator stack with structured `DomainError` → HTTP mapping
- **Quality gate**: 1131 tests (1058 unit + 71 integration + 2 component), 91% coverage, ruff (lint), mypy (typecheck) — all gated in `make ci`
- **Reproducibility**: everything runs in Docker; `Makefile` is the single entry point

---

## Where to go next

📍 **You're new and just want to use it** → [`docs/en/user_guide.md`](./docs/en/user_guide.md) ([🇺🇦](./docs/ua/user_guide.md))
   Pages, input limits, expected timing, costs, errors, FAQ.

🎓 **You're reviewing this for academic context** → [`docs/en/system_overview_for_readers.md`](./docs/en/system_overview_for_readers.md) ([🇺🇦](./docs/ua/system_overview_for_readers.md))
   "What is this and why" in plain language, no implementation details.

🛠️ **You're a contributor / developer** → [`docs/en/system_overview.md`](./docs/en/system_overview.md) ([🇺🇦](./docs/ua/system_overview.md))
   Full 16-section walkthrough: every component, every interface, every decision.

🔬 **You're a researcher running ablations** → [`docs/en/evaluation_harness.md`](./docs/en/evaluation_harness.md) ([🇺🇦](./docs/ua/evaluation_harness.md))
   18 scenarios × 8 configs harness, batch runner, paired-Δ analysis.

🧠 **Algorithm deep-dives** → [meter](./docs/en/meter_validation.md) · [rhyme](./docs/en/rhyme_validation.md) · [stress](./docs/en/stress_and_syllables.md) · [detection](./docs/en/detection_algorithm.md) · [feedback loop](./docs/en/feedback_loop.md) · [LLM decorator stack](./docs/en/llm_decorator_stack.md)

🏛️ **Architectural decisions** → [`docs/adr/`](./docs/adr/)

> Documentation is bilingual (UA + EN), kept in sync.

---

## Programmatic use

If you want to integrate this into your own pipeline rather than use the web UI:

```python
from src.composition_root import build_poetry_service
from src.config import AppConfig
from src.domain.models import (
    GenerationRequest, MeterSpec, PoemStructure, RhymeScheme,
)

service = build_poetry_service(AppConfig.from_env())

result = service.generate(GenerationRequest(
    theme="весна у лісі, пробудження природи",
    meter=MeterSpec(name="ямб", foot_count=4),
    rhyme=RhymeScheme(pattern="ABAB"),
    structure=PoemStructure(stanza_count=1, lines_per_stanza=4),
    max_iterations=2,
))

print(result.poem)
print(f"meter {result.validation.meter.accuracy:.0%} · "
      f"rhyme {result.validation.rhyme.accuracy:.0%}")
```

There is also a JSON API — see Swagger at http://localhost:8000/docs once `make serve` is up.

---

## Project layout

```
src/
├── domain/            # pure-Python models + ports (interfaces)
├── infrastructure/    # adapters: validators, LLM, retrieval, tracing, persistence
├── services/          # use-case façades (PoetryService, EvaluationService, ...)
├── handlers/
│   ├── api/           # FastAPI JSON routes
│   └── web/           # Jinja-template pages
└── composition_root.py  # DI wiring
docs/                  # bilingual documentation
data/                  # raw .txt poems (corpus source)
corpus/                # built-and-versioned theme + metric corpora (JSON)
tests/                 # unit (1058) + integration (71) + component (2) tests
results/               # batch run outputs (gitignored)
```

Clean-architecture layers; the inner layers (`domain`, `services`) have no infrastructure imports.

---

## Common commands

| Command | What it does |
|---------|---------------|
| `make serve` | Start the web UI at http://localhost:8000 |
| `make test` | Run all tests in Docker |
| `make ci` | Lint + typecheck + tests (the full CI gate) |
| `make demo` | Run a default scenario through the full pipeline, print trace |
| `make ablation` | Run 18 × 8 × 3 = 432 ablation runs (~\$25–50 on Gemini Flash) |
| `make ablation-cheap` | Same as `ablation` but `SEEDS=1` (~\$8–15, ~90% of the signal) |
| `make ablation-report RUNS=results/batch_…/runs.csv` | Build PNG plots + dashboard data |
| `make build-theme-corpus-with-embeddings` | Rebuild the theme RAG corpus from raw `data/` |

Full Makefile reference: `make help` (or just open `Makefile` — it's heavily commented).

---

## Configuration (essentials)

Most settings work out of the box. The only required env var is `GEMINI_API_KEY`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `GEMINI_API_KEY` | — | Google Gemini key (required for generation). See setup recipe in [Try it in 60 seconds § Option A](#option-a--full-system-with-real-gemini-recommended) |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | Model name. **Paid** (~\$2/1M in, ~\$12/1M out). For free smoke-testing: `gemini-2.5-flash` (significantly worse quality for poetry) |
| `LLM_TIMEOUT_SEC` | `120` | Per-call hard timeout. 120s suits Pro reasoning models; drop to 20s if you switch to Flash |
| `OFFLINE_EMBEDDER` | `false` | `true` → skip LaBSE download (deterministic stub for tests/offline dev) |

Full table + reasoning-model caveats: [`docs/en/reliability_and_config.md`](./docs/en/reliability_and_config.md).

---

## Status

- ✅ **1131 tests** (1058 unit + 71 integration + 2 component) — `make ci` green
- ✅ **91% line coverage**, 84% branch coverage
- ✅ **No type errors** (mypy strict on `src/` and `tests/`)
- ✅ **Reproducible**: Docker + Poetry lock + deterministic offline embedder fallback
- ✅ **Bilingual documentation** (UA + EN) covering every component and contract

---

## Academic context

MSc thesis project, 2026. Demonstrates:

- **Hybrid AI architecture**: combining neural text generation with symbolic linguistic verification.
- **Quantitative ablation**: paired-Δ design with bootstrap CIs measures each component's marginal contribution.
- **Clean-architecture discipline**: hexagonal layout with strict port/adapter separation, testable in isolation.

Cite as a research artefact, fork as a starter for similar pipelines on other Slavic / morphologically rich languages.

---

## License

This project is released under the **[PolyForm Noncommercial License 1.0.0](./LICENSE)** — see [`LICENSE`](./LICENSE) for the full text.

In short:

| Use case | Allowed under this licence? |
|----------|------------------------------|
| Personal research, study, hobby projects | ✅ Yes (free) |
| Academic / non-profit / educational research | ✅ Yes (free) — please cite (see [`CITATION.cff`](./CITATION.cff)) |
| Public-sector, government, NGO use | ✅ Yes (free) |
| Modifying, forking, redistributing for the above | ✅ Yes (with attribution + same licence) |
| Integrating into a commercial product / SaaS / paid service | ❌ Requires a separate commercial licence |
| Selling derivatives or revenue-generating use | ❌ Requires a separate commercial licence |

**For commercial use:** contact **olhadziuhal@gmail.com** — commercial licensing is offered on reasonable terms.

The Ukrainian poetry source texts in `data/` are not covered by this licence and remain subject to their authors' copyright (most pre-1953 authors are in the public domain in Ukraine; later authors may not be). See `LICENSE` § *Scope* for details.
