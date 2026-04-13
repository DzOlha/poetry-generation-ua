# ── Лінтер ───────────────────────────────────────────────────────────────────
#
#   make lint        — перевірити src/ і tests/ (тільки помилки, без автовиправлення)
#   make lint-fix    — автовиправити те, що можна (isort, unused imports тощо)

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

# ── Full quality gate ────────────────────────────────────────────────────────
#
#   make ci          — run lint + typecheck + tests (everything the CI pipeline should run)

ci: lint typecheck test

# ── Контейнер ─────────────────────────────────────────────────────────────────

# Підняти контейнер для dev
up:
	docker compose -f docker/docker-compose.yml up -d --build

# Зайти в контейнер (з активованим Poetry virtualenv)
bash:
	docker compose -f docker/docker-compose.yml run --rm poetry bash

# Запустити демо-пайплайн через Poetry
pipeline:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run python scripts/run_pipeline.py

# Запустити Web UI (FastAPI + Jinja2)
serve:
	docker compose -f docker/docker-compose.yml run --rm --service-ports poetry \
		poetry run uvicorn src.handlers.api.app:app --host 0.0.0.0 --port 8000 --reload

# Зупинити і видалити контейнер та томи
down:
	docker compose -f docker/docker-compose.yml down --volumes --remove-orphans

# Завантажити Stanza-ресурси (≈500 МБ, потрібно один раз; кешується у Docker volume)
preload-stanza:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run python scripts/preload_stanza.py

# Запустити всі тести в контейнері (спочатку завантажує словник, потім тести)
test:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/ -v"

# Тільки unit-тести
test-unit:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/unit/ -v"

# Тільки інтеграційні тести
test-integration:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && poetry run python -m pytest tests/integration/ -v -m integration"

# ── Demo (швидкий наочний запуск повної системи) ─────────────────────────────
#
#   make demo                    — запустити N01 (весна, ямб 4ст ABAB) через повну систему (конфіг E)
#   make demo SCENARIO=N03       — будь-який інший сценарій

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

# ── Оцінка (конфігурується через змінні) ─────────────────────────────────────
#
#   make evaluate                                  — всі сценарії × всі конфіги (90 запусків)
#   make evaluate SCENARIO=N01                     — один сценарій, всі конфіги
#   make evaluate SCENARIO=N01 CONFIG=E            — один сценарій, повна система
#   make evaluate CONFIG=E                         — всі сценарії, повна система
#   make evaluate CATEGORY=corner                  — тільки corner-кейси
#   make evaluate SCENARIO=N01 CONFIG=E VERBOSE=1  — з детальними трейсами
#   make evaluate OUTPUT=results/my_run.json       — конкретний файл для результатів

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

# ── Corpus management ────────────────────────────────────────────────────────
#
# Тематичний корпус (uk_theme_reference_corpus.json) — вірші + LaBSE-ембедінги
# для семантичного пошуку за темою:
#   make build-theme-corpus
#   make build-theme-corpus DATA_DIR=data THEME_OUT=corpus/uk_theme_reference_corpus.json MIN_COUNT=1
#
# Обрахувати LaBSE-ембедінги для існуючого тематичного корпусу (окремо):
#   make embed-theme-corpus
#   make embed-theme-corpus THEME_CORPUS=corpus/uk_theme_reference_corpus.json
#
# Побудувати тематичний корпус І одразу обрахувати ембедінги (один крок):
#   make build-theme-corpus-with-embeddings
#
# Метрично-римний корпус (uk_auto_metric_corpus.json) — вірші з автоматично
# розпізнаним метром і схемою рими (brute-force detection по data/):
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

# Перебудувати образ без кешу
rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache
