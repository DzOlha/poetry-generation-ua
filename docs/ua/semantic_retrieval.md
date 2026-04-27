# Семантичний пошук (RAG)

> Як система знаходить кілька тематично близьких віршів із корпусу і вставляє їх у промпт як натхнення для моделі. Це — Retrieval-Augmented Generation в українській поетичній постановці.

## Навіщо

Промпт без контексту: «Напиши вірш про весну». Результат: модель зображує узагальнений вірш, часто шаблонний і не схожий на українську традицію.

Промпт із RAG: «Напиши вірш про весну. Ось два приклади української поезії про щось близьке: [Шевченко], [Тичина]. Не копіюй, але візьми дух і тон.» Результат: вірш ближче до української літературної школи, з природною лексикою.

Важливо: ми не просимо модель **копіювати** приклади. Ми даємо їй **стиль-орієнтир**. Це підтверджено в інструкціях промпту явно.

## Ідея

На кожен вірш у нашому корпусі ми заздалегідь порахували **семантичний вектор** (embedding) — числовий запис змісту у багатовимірному просторі. Якщо два вірші близькі семантично — їхні вектори близькі (малий кут між ними). Якщо далекі — вектори далекі.

При запиті:
1. Перетворюємо тему у такий самий вектор.
2. Для кожного вірша у корпусі рахуємо косинус кута між вектором теми і вектором вірша.
3. Сортуємо за спаданням косинуса (від 1.0 = ідентичний напрямок до 0.0 = перпендикулярний).
4. Беремо **5 найближчих** (top-k).

Два з цих пʼяти (або інша кількість за налаштуванням) інжектяться у промпт як тематичні приклади.

## Модель embeddings: LaBSE

Використовується [`sentence-transformers/LaBSE`](https://huggingface.co/sentence-transformers/LaBSE) від Google — Language-agnostic BERT Sentence Embedding. Навчена на 109 мовах, включно з українською, на 6 мільярдах перекладених пар.

Характеристики:
- **Розмірність вектора:** 768
- **Нормалізація:** вектори нормалізовані до одиничної довжини (`||v|| = 1`). Тому косинус схожості = просто скалярний добуток.
- **Модель:** ~1.9 ГБ. Завантажується лазиво при першому виклику через `sentence-transformers` бібліотеку.
- **Інференс:** CPU працює, GPU прискорює на ~5-10×. Один вірш — десяті долі секунди.

Реалізація: [`LaBSEEmbedder`](../../src/infrastructure/embeddings/labse.py).

## Архітектура з fallback

LaBSE потрібна мережа (HuggingFace download при першому запуску). Це не завжди доступно: CI без інтернету, pre-commit hooks, оффлайн розробка. Composition root тому інжектить одну з двох форм залежно від прапорця `OFFLINE_EMBEDDER` (див. [`generation_data_plane.py`](../../src/infrastructure/composition/generation_data_plane.py)):

- `OFFLINE_EMBEDDER=true` → `embedder()` контейнера повертає `OfflineDeterministicEmbedder` напряму. `CompositeEmbedder` не будується взагалі.
- `OFFLINE_EMBEDDER=false` (дефолт) → `CompositeEmbedder(primary=LaBSEEmbedder, fallback=OfflineDeterministicEmbedder)`.

[`CompositeEmbedder`](../../src/infrastructure/embeddings/composite.py) при `encode(text)`:
1. Спроба через primary (LaBSE).
2. Якщо `EmbedderError` (модель відсутня, мережа лежить, OOM) → **переключитися на fallback назавжди** у цьому процесі. Лог попередження один раз.
3. Наступні виклики йдуть одразу у fallback (без повторних спроб primary).

### OfflineDeterministicEmbedder

[`OfflineDeterministicEmbedder`](../../src/infrastructure/embeddings/labse.py) — fallback, що **не робить справжнього NLP**. Працює так:

```python
def encode(text: str) -> list[float]:
    rng = random.Random(abs(hash(text)) % (2**32))
    vec = [rng.gauss(0, 1) for _ in range(768)]
    norm = sqrt(sum(x**2 for x in vec))
    return [x / norm for x in vec]
```

Hash → seed для детермінованого RNG → 768 гаусових чисел → нормалізація.

Властивості:
- **Детермінованість:** ті ж тексти дають ті ж вектори. Тести, CI, regression-перевірки стабільні.
- **Жодного семантичного змісту.** Близькість двох векторів випадкова. Retrieval у offline-режимі **не повертає** тематично близькі вірші — повертає перші 5 за хеш-подібністю, що по факту рандом.
- **Ідеально для unit-тестів.** Pipeline тестується як цілісна конструкція, без залежності від ~2 ГБ моделі.

У продакшені це означає: **якщо LaBSE впав, semantic_relevance метрика стане шумом**, але pipeline не зламається і видасть якийсь результат. Лог про це буде попереджати.

## Корпус: формат і підготовка

Корпус — JSON-файл ([`corpus/uk_theme_reference_corpus.json`](../../corpus/uk_theme_reference_corpus.json)). Структура:

```json
[
  {
    "id": "shevchenko-0001",
    "text": "Садок вишневий коло хати,\nХрущі над вишнями гудуть,\nПлугатарі з плугами йдуть,\nСпівають ідучи дівчата...",
    "author": "Тарас Шевченко",
    "theme": "сільський вечір, природа",
    "embedding": [0.0134, -0.0072, 0.0456, ...  // 768 елементів
  },
  ...
]
```

**Поле `embedding`** — попередньо обчислений вектор. Зберігаємо у корпусі, щоб під час запиту не робити 1000+ викликів до LaBSE. На запит вираховуємо вектор **тільки для теми** (один раз) і порівнюємо з усіма збереженими.

[`JsonThemeRepository.load`](../../src/infrastructure/repositories/theme_repository.py) читає цей файл і будує `ThemeExcerpt` (id, text, author, theme, кортеж embedding). Якщо файлу немає — composition root підставляє `DemoThemeRepository` (мінімальний набір зашитих уривків Шевченка); pipeline працює, просто з деградованим retrieval.

Побудова корпусу — окремий offline-workflow через Makefile:
```bash
make build-theme-corpus DATA_DIR=data/public-domain-poems    # лише тексти
make build-theme-corpus-with-embeddings                      # тексти + LaBSE-ембеддинги
```

Другий target і дає продакшн-готовий `corpus/uk_theme_reference_corpus.json`, який споживає `JsonThemeRepository`.

## Retrieval: як саме ранжируємо

[`SemanticRetriever`](../../src/infrastructure/retrieval/semantic_retriever.py) реалізує порт `IRetriever`. Реальна сигнатура — `retrieve(theme, corpus, top_k=5)`:

```python
class SemanticRetriever(IRetriever):
    def __init__(self, embedder: IEmbedder) -> None:
        self._embedder = embedder

    def retrieve(
        self, theme: str, corpus: list[ThemeExcerpt], top_k: int = 5,
    ) -> list[RetrievedExcerpt]:
        query_vec = self._embedder.encode(theme)
        ranked = sorted(
            (self._score(query_vec, excerpt) for excerpt in corpus),
            key=lambda x: x.similarity,
            reverse=True,
        )
        return ranked[: max(1, top_k)]
```

Для кожного уривка retriever бере `excerpt.embedding`, якщо він є; інакше лазиво кодує `excerpt.text`. Косинус — `dot(a, b) / (||a|| * ||b||)`; оскільки LaBSE віддає нормалізовані вектори (`||v|| = 1`), це вироджується у звичайний dot product — копійка CPU.

Повертається `list[RetrievedExcerpt]`:
- `excerpt` — value object `ThemeExcerpt` із текстом і метаданими.
- `similarity` — число у `[-1, 1]`, практично в `[0, 1]` для нормалізованих ембеддингів.

## Інтеграція у pipeline

`RetrievalStage` у [`src/infrastructure/stages/retrieval_stage.py`](../../src/infrastructure/stages/retrieval_stage.py):

1. Зчитує `IThemeRepository.load()` → список віршів корпусу.
2. Викликає `retriever.retrieve(theme, corpus, top_k=5)`.
3. Записує `state.retrieved` (список `RetrievedExcerpt`).
4. Наступний `PromptStage` передає уривки у [`RagPromptBuilder`](../../src/infrastructure/prompts/rag_prompt_builder.py), який інжектує перші 2 (за замовчуванням) у промпт як стилеві орієнтири.

Retriever, репозиторії і embedder проводяться у [`generation_data_plane.py`](../../src/infrastructure/composition/generation_data_plane.py); LLM-стек — у `generation_llm_stack.py`; самі pipeline-стейджі — у `generation_pipeline_stages.py`.

Кількість пошукуваних (`k=5`) і кількість інжектованих (`top_k=2`) — різні параметри:
- 5 для діагностики / UI — видно, що підібрав retriever.
- 2 у промпт — бо понад 2 приклади вже перевантажують промпт і модель починає копіювати.

## Паралель із метричним retriever-ом

Є **другий** retrieval-шар — `MetricExamplesStage` — який витягує з окремого корпусу приклади з потрібним метром і римою (**не семантично**, а точним запитом meter+foot_count+rhyme). Це **не** використовує embeddings; це SQL-подібний filter-запит. Детальніше — у [`prompt_construction.md`](./prompt_construction.md).

## Ключові файли

- [`src/infrastructure/retrieval/semantic_retriever.py`](../../src/infrastructure/retrieval/semantic_retriever.py) — `SemanticRetriever` (реалізація `IRetriever`)
- [`src/infrastructure/embeddings/labse.py`](../../src/infrastructure/embeddings/labse.py) — `LaBSEEmbedder` (768-d, sentence-transformers) і `OfflineDeterministicEmbedder` (test/CI fallback)
- [`src/infrastructure/embeddings/composite.py`](../../src/infrastructure/embeddings/composite.py) — `CompositeEmbedder` runtime fallback chain
- [`src/infrastructure/repositories/theme_repository.py`](../../src/infrastructure/repositories/theme_repository.py) — `JsonThemeRepository` / `DemoThemeRepository` / `InMemoryThemeRepository`
- [`src/infrastructure/composition/generation_data_plane.py`](../../src/infrastructure/composition/generation_data_plane.py) — звʼязки репозиторіїв, embedder-а (з перемикачем `OFFLINE_EMBEDDER`), retriever-а
- [`src/infrastructure/stages/retrieval_stage.py`](../../src/infrastructure/stages/retrieval_stage.py) — pipeline-інтеграція
- [`corpus/uk_theme_reference_corpus.json`](../../corpus/uk_theme_reference_corpus.json) — сам корпус (будується через `make build-theme-corpus-with-embeddings`)

## Налаштування

| Параметр | Де | Дефолт |
|----------|-----|--------|
| Шлях до корпусу | `CORPUS_PATH` (env) | `corpus/uk_theme_reference_corpus.json` |
| Модель embeddings | `LABSE_MODEL` (env) | `sentence-transformers/LaBSE` |
| Режим offline | `OFFLINE_EMBEDDER=true` | `false` (використовує LaBSE) |
| top-k retrieval | `GenerationRequest.top_k` | `5` |
| Інжектується у промпт | `GenerationRequest.metric_examples_top_k` (так, неточна назва — для тематики також використовується) | `2` |

## Тонкощі

- **Ліниве завантаження LaBSE.** При першому виклику в контейнері ~10-30 сек йдуть на завантаження моделі. На сторінці генерації це відображається у спінері. Наступні виклики — десяті долі секунди.
- **Кеш HuggingFace.** Модель скачується один раз і кешується у `~/.cache/huggingface/`. Docker том `hf_cache` у [`docker-compose.yml`](../../docker/docker-compose.yml) зберігає кеш між запусками.
- **Якість корпусу критична.** Сміттєвий корпус = сміттєві приклади → сміттєва генерація. Тому є `MIN_COUNT`, фільтр довжини у `build-theme-corpus` скрипті.
- **Без українського корпусу можна, але погано.** Система підтримує інші мови (LaBSE багатомовна), але тоді треба подати відповідний JSON. Без корпусу retrieval повертає порожній список → промпт будується без тематичних прикладів → якість падає.

## Див. також

- [`prompt_construction.md`](./prompt_construction.md) — як retrieval інтегрується у промпт.
- [`evaluation_harness.md`](./evaluation_harness.md) — метрика `semantic_relevance` оцінює, наскільки фінальний вірш залишився семантично близький до теми.
- [`system_overview_for_readers.md`](./system_overview_for_readers.md) §4 — висоякорівневе пояснення семантичного пошуку.
