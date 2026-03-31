# ── Лінтер ───────────────────────────────────────────────────────────────────
#
#   make lint        — перевірити src/ і tests/ (тільки помилки, без автовиправлення)
#   make lint-fix    — автовиправити те, що можна (isort, unused imports тощо)

lint:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run ruff check src/ tests/

lint-fix:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run ruff check --fix src/ tests/

# ── Контейнер ─────────────────────────────────────────────────────────────────

# Підняти контейнер для dev
up:
	docker compose -f docker/docker-compose.yml up -d --build

# Зайти в контейнер (з активованим Poetry virtualenv)
bash:
	docker compose -f docker/docker-compose.yml run --rm poetry bash

# Запустити пайплайн через Poetry
pipeline:
	docker compose -f docker/docker-compose.yml run --rm poetry poetry run python scripts/run_pipeline.py

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
#   make demo                    — запустити N01 (весна, ямб 4ст ABAB) через повну систему
#   make demo SCENARIO=N03       — будь-який інший сценарій

_TS := $(shell date +%Y%m%d_%H%M%S)

demo:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/preload_stanza.py && \
		 poetry run python scripts/run_evaluation.py \
		   --scenario $(if $(SCENARIO),$(SCENARIO),N01) \
		   --config F \
		   --verbose \
		   --stanzas 2 \
		   --lines-per-stanza 4 \
		   -o results/demo_$(if $(SCENARIO),$(SCENARIO),N01)_$(_TS).json"

# ── Оцінка (конфігурується через змінні) ─────────────────────────────────────
#
#   make evaluate                                  — всі сценарії × всі конфіги (108 запусків)
#   make evaluate SCENARIO=N01                     — один сценарій, всі конфіги
#   make evaluate SCENARIO=N01 CONFIG=F            — один сценарій, повна система
#   make evaluate CONFIG=F                         — всі сценарії, повна система
#   make evaluate CATEGORY=corner                  — тільки corner-кейси
#   make evaluate SCENARIO=N01 CONFIG=F VERBOSE=1  — з детальними трейсами
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
# Побудувати корпус із сирих .txt-файлів у data/ (без ембедінгів):
#   make build-corpus
#   make build-corpus DATA_DIR=data OUT=corpus/uk_poetry_corpus.json MIN_COUNT=1
#
# Обрахувати LaBSE-ембедінги для існуючого корпусу (окремо):
#   make embed-corpus
#   make embed-corpus CORPUS=corpus/uk_poetry_corpus.json
#
# Побудувати корпус І одразу обрахувати ембедінги (один крок):
#   make build-corpus-with-embeddings
#   make build-corpus-with-embeddings DATA_DIR=data OUT=corpus/uk_poetry_corpus.json MIN_COUNT=1

DATA_DIR  ?= data
OUT       ?= corpus/uk_poetry_corpus.json
MIN_COUNT ?= 1
CORPUS    ?= corpus/uk_poetry_corpus.json

build-corpus:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_corpus_from_data_dir.py \
		  --data-dir $(DATA_DIR) \
		  --out $(OUT) \
		  --min-count $(MIN_COUNT)"

embed-corpus:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_corpus_embeddings.py \
		  --corpus $(CORPUS)"

build-corpus-with-embeddings:
	docker compose -f docker/docker-compose.yml run --rm poetry bash -c \
		"poetry run python scripts/build_corpus_from_data_dir.py \
		  --data-dir $(DATA_DIR) \
		  --out $(OUT) \
		  --min-count $(MIN_COUNT) \
		  --embed"

# Перебудувати образ без кешу
rebuild:
	docker compose -f docker/docker-compose.yml build --no-cache
