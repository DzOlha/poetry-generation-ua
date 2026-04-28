# ── Linter ───────────────────────────────────────────────────────────────────
#
#   make lint        — check src/ and tests/ (errors only, no autofix)
#   make lint-fix    — autofix what can be fixed (isort, unused imports, etc.)

lint:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run ruff check src/ tests/

lint-fix:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run ruff check --fix src/ tests/

# ── Type checking ────────────────────────────────────────────────────────────
#
#   make typecheck   — run mypy over src/ and tests/

typecheck:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run mypy src/ tests/

# ── Coverage ─────────────────────────────────────────────────────────────────
#
#   make coverage    — run full test suite with coverage reporting

coverage:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && \
		 poetry run python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html"

# ── Markdown link check ──────────────────────────────────────────────────────
#
#   make check-links — scan all .md files for broken internal links (relative
#                      file paths between docs) using lychee in --offline mode.
#                      External URLs are skipped to keep the check fast and
#                      deterministic. Excludes generated artefacts:
#                      results/, htmlcov*/, .pytest_cache/, .git/, .venv/.

check-links:
	docker run --rm --init -v $(PWD):/input:ro -w /input lycheeverse/lychee:latest \
		--offline \
		--no-progress \
		--exclude-path results \
		--exclude-path htmlcov \
		--exclude-path htmlcov-unit \
		--exclude-path .pytest_cache \
		--exclude-path .git \
		--exclude-path .venv \
		'**/*.md'

# ── Full quality gate ────────────────────────────────────────────────────────
#
#   make ci          — run lint + typecheck + tests (everything the CI pipeline should run)

ci: lint typecheck test

# ── Container ────────────────────────────────────────────────────────────────

# Bring up the dev container
up:
	docker compose -f docker/docker-compose.yml up -d --build

# Open a shell inside the container (with Poetry virtualenv activated)
bash:
	docker compose -f docker/docker-compose.yml run --rm poetry bash

# Run the demo pipeline via Poetry
pipeline:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run python scripts/run_pipeline.py

# Run the Web UI (FastAPI + Jinja2)
serve:
	docker compose -f docker/docker-compose.yml run --rm --service-ports poetry \
		poetry run uvicorn src.handlers.api.app:app --host 0.0.0.0 --port 8000 --reload

# Stop and remove the container and volumes
down:
	docker compose -f docker/docker-compose.yml down --volumes --remove-orphans

# Download Stanza resources (~500 MB, needed once; cached in a Docker volume)
preload-stanza:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run python scripts/preload_stanza.py

# Run ALL tests in the container (including component tests that download
# the real LaBSE model, ~1.8 GB on first run). The first `make test` after
# a fresh image/volume takes ~5 min for the HF cache download; subsequent
# runs are fast — the model is already in the Docker volume.
# To skip heavy component tests (for CI without network or pre-commit),
# run `make test-unit && make test-integration` separately.
test:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/ -v"

# Unit tests only
test-unit:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/unit/ -v"

# Integration tests only
test-integration:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/integration/ -v -m integration"

# Component tests: real LaBSE model, etc. Requires network for the first
# download (~1.8 GB into the HF cache). NOT run in the regular `make test`
# / CI — local-only before a release.
test-component:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/component/ -v -m component"

# ── Demo (quick end-to-end run of the full system) ───────────────────────────
#
#   make demo                    — run N01 (spring, iambic tetrameter ABAB) through the full system (config E)
#   make demo SCENARIO=N03       — any other scenario

_TS := $(shell date +%Y%m%d_%H%M%S)

demo:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && \
		 poetry run python scripts/run_evaluation.py \
		   --scenario $(if $(SCENARIO),$(SCENARIO),N01) \
		   --config E \
		   --verbose \
		   --stanzas 2 \
		   --lines-per-stanza 4 \
		   -o results/demo_$(if $(SCENARIO),$(SCENARIO),N01)_$(_TS).json"

# ── Evaluation (configurable via variables) ──────────────────────────────────
#
#   make evaluate                                  — all 18 scenarios × 8 configs = 144 runs
#   make evaluate SCENARIO=N01                     — one scenario, all configs
#   make evaluate SCENARIO=N01 CONFIG=E            — one scenario, full system
#   make evaluate CONFIG=E                         — all scenarios, full system
#   make evaluate CATEGORY=corner                  — corner cases only
#   make evaluate SCENARIO=N01 CONFIG=E VERBOSE=1  — with detailed traces
#   make evaluate OUTPUT=results/my_run.json       — specific output file

SCENARIO        ?=
CONFIG          ?=
CATEGORY        ?=
VERBOSE         ?=
OUTPUT          ?= results/eval_$(_TS).json
STANZAS         ?= 2
LINES_PER_STANZA ?= 4

_EVAL_ARGS :=
ifneq ($(SCENARIO),)
  _EVAL_ARGS += --scenario $(SCENARIO)
endif
ifneq ($(CONFIG),)
  _EVAL_ARGS += --config $(CONFIG)
endif
ifneq ($(CATEGORY),)
  _EVAL_ARGS += --category $(CATEGORY)
endif
ifneq ($(VERBOSE),)
  _EVAL_ARGS += -v
endif
ifneq ($(OUTPUT),)
  _EVAL_ARGS += -o $(OUTPUT)
endif
ifneq ($(STANZAS),)
  _EVAL_ARGS += --stanzas $(STANZAS)
endif
ifneq ($(LINES_PER_STANZA),)
  _EVAL_ARGS += --lines-per-stanza $(LINES_PER_STANZA)
endif

evaluate:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python scripts/run_evaluation.py $(_EVAL_ARGS)"

# ── Ablation batch (scenarios × configs × seeds → flat CSV) ─────────────────
#
#   make ablation                                         — all 18 scenarios × 8 configs × 3 seeds (432 runs)
#   make ablation-cheap                                   — same but SEEDS=1 (144 runs, ~$8-15 Flash)
#                                                            For pilot runs / quick hypothesis preview.
#                                                            Loses per-cell CI; corpus-wide signal stays ~90% intact.
#   make ablation SEEDS=5                                 — more repetitions per cell
#   make ablation CATEGORY=edge                           — edge scenarios only
#   make ablation SCENARIO=N01 CONFIG=E SEEDS=10          — one cell, many repetitions
#   make ablation BATCH_DIR=results/my_run                — specific folder instead of batch_<ts>
#   make ablation DELAY=5                                 — 5 s between requests (fewer rate-limit errors)
#   make ablation MAX_ITERATIONS=2                        — up to 2 feedback regens after initial gen
#   make ablation SKIP_DEGENERATE=1                       — skip C04/C08 (quota saver)
#
# Resume after a quota hit / failure: pass the same folder and RESUME=1.
# Already-successful rows are kept; only failed or unreached cells re-run:
#   make ablation BATCH_DIR=results/batch_20260424_180000 RESUME=1
#
# Output: $(BATCH_DIR)/runs.csv — one row per run, consumed by
# analyze_contributions (Stage 2) and the /ablation-report web page (Stage 3).

SEEDS           ?= 3
DELAY           ?= 3
MAX_ITERATIONS  ?= 1
RESUME          ?=
SKIP_DEGENERATE ?=
BATCH_DIR       ?= results/batch_$(_TS)

_ABL_ARGS := --seeds $(SEEDS) --delay $(DELAY) \
             --max-iterations $(MAX_ITERATIONS) \
             --output $(BATCH_DIR)/runs.csv
ifneq ($(SCENARIO),)
  _ABL_ARGS += --scenario $(SCENARIO)
endif
ifneq ($(CONFIG),)
  _ABL_ARGS += --config $(CONFIG)
endif
ifneq ($(CATEGORY),)
  _ABL_ARGS += --category $(CATEGORY)
endif
ifneq ($(RESUME),)
  _ABL_ARGS += --resume
endif
ifneq ($(SKIP_DEGENERATE),)
  _ABL_ARGS += --skip-degenerate
endif

ablation:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python scripts/run_batch_evaluation.py $(_ABL_ARGS)"

# Pilot variant: one seed per cell. ~144 runs instead of 432, ~30% of
# the time and cost. Good for a hypothesis-preview pass. If an
# interesting effect shows up, re-run with full SEEDS=3 for statistics.
ablation-cheap:
	$(MAKE) ablation SEEDS=1

# ── Ablation report (component contributions + PNG charts) ───────────────────
#
#   make ablation-report RUNS=results/batch_20260421_190000/runs.csv
#
# Writes into the same folder as runs.csv and generates:
#   contributions.csv, contributions_by_cat.csv, report.json, plots/*.png
#
# Open in browser: `make serve` → http://localhost:8000/ablation-report

RUNS ?=

ablation-report:
	@if [ -z "$(RUNS)" ]; then \
		echo "RUNS is required. Example: make ablation-report RUNS=results/batch_20260421_190000/runs.csv"; \
		exit 1; \
	fi
	docker compose -f docker/docker-compose.yml run --rm poetry \
		poetry run python scripts/analyze_contributions.py --runs $(RUNS)

# ── Corpus management ────────────────────────────────────────────────────────
#
# Theme corpus (uk_theme_reference_corpus.json) — poems + LaBSE embeddings
# for semantic theme search:
#   make build-theme-corpus
#   make build-theme-corpus DATA_DIR=data THEME_OUT=corpus/uk_theme_reference_corpus.json MIN_COUNT=1
#
# Compute LaBSE embeddings for an existing theme corpus (separately):
#   make embed-theme-corpus
#   make embed-theme-corpus THEME_CORPUS=corpus/uk_theme_reference_corpus.json
#
# Build the theme corpus AND compute embeddings in one step:
#   make build-theme-corpus-with-embeddings
#
# Metric-rhyme corpus (uk_auto_metric_corpus.json) — poems with
# auto-detected meter and rhyme scheme (brute-force detection over data/):
#   make build-metric-corpus
#   make build-metric-corpus DATA_DIR=data METRIC_OUT=corpus/uk_auto_metric_corpus.json

DATA_DIR       ?= data
THEME_OUT      ?= corpus/uk_theme_reference_corpus.json
MIN_COUNT      ?= 1
THEME_CORPUS   ?= corpus/uk_theme_reference_corpus.json
METRIC_OUT     ?= corpus/uk_auto_metric_corpus.json
SAMPLE_LINES   ?=

build-theme-corpus:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_corpus_from_data_dir.py \
		  --data-dir $(DATA_DIR) \
		  --out $(THEME_OUT) \
		  --min-count $(MIN_COUNT)"

embed-theme-corpus:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_corpus_embeddings.py \
		  --corpus $(THEME_CORPUS)"

build-theme-corpus-with-embeddings:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_corpus_from_data_dir.py \
		  --data-dir $(DATA_DIR) \
		  --out $(THEME_OUT) \
		  --min-count $(MIN_COUNT) \
		  --embed"

build-metric-corpus:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_metric_corpus.py \
		  --data-dir $(DATA_DIR) \
		  --out $(METRIC_OUT) \
		  $(if $(SAMPLE_LINES),--sample-lines $(SAMPLE_LINES),)"

# ── Aggregate batch runs.csv into Markdown summary tables ───────────────────
#
#   make aggregate-runs RUNS=results/batch_20260426_220040/runs.csv
#     — write TWO combined reports for ALL ablation configs (A–H present in
#       runs.csv): UA captions to <batch_dir>/aggregates.ua.md and EN
#       captions to <batch_dir>/aggregates.en.md.  Suitable for committing
#       alongside the runs and for pasting into chapter 4 of the thesis.
#
#   make aggregate-runs RUNS=... CONFIG=A
#     — render ONLY one config and print to stdout (no file written).
#       Add LANG=en to switch captions to English (default: ua).
#
#   make aggregate-runs RUNS=... LANG=en
#     — produce only the English file.  LANG=ua produces only the Ukrainian.

AGG_OUT ?=
LANG    ?=

aggregate-runs:
	@if [ -z "$(RUNS)" ]; then \
		echo "RUNS is required. Example: make aggregate-runs RUNS=results/batch_.../runs.csv"; \
		exit 1; \
	fi
	@if [ -n "$(CONFIG)" ]; then \
		LANG_ARG="$(if $(LANG),$(LANG),ua)"; \
		docker compose -f docker/docker-compose.yml run --rm poetry \
		  poetry run python scripts/aggregate_runs.py \
		    --runs $(RUNS) --config $(CONFIG) --lang $$LANG_ARG; \
	elif [ "$(LANG)" = "ua" ]; then \
		OUT="$(if $(AGG_OUT),$(AGG_OUT),$(dir $(RUNS))aggregates.ua.md)"; \
		docker compose -f docker/docker-compose.yml run --rm poetry \
		  poetry run python scripts/aggregate_runs.py \
		    --runs $(RUNS) --lang ua --output $$OUT; \
	elif [ "$(LANG)" = "en" ]; then \
		OUT="$(if $(AGG_OUT),$(AGG_OUT),$(dir $(RUNS))aggregates.en.md)"; \
		docker compose -f docker/docker-compose.yml run --rm poetry \
		  poetry run python scripts/aggregate_runs.py \
		    --runs $(RUNS) --lang en --output $$OUT; \
	else \
		UA_OUT="$(dir $(RUNS))aggregates.ua.md"; \
		EN_OUT="$(dir $(RUNS))aggregates.en.md"; \
		docker compose -f docker/docker-compose.yml run --rm poetry bash -c " \
		  poetry run python scripts/aggregate_runs.py \
		    --runs $(RUNS) --lang ua --output $$UA_OUT && \
		  poetry run python scripts/aggregate_runs.py \
		    --runs $(RUNS) --lang en --output $$EN_OUT"; \
	fi

# Rebuild the image without cache
rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache
