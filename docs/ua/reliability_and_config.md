# Надійність і конфігурація

> Всі runtime-налаштування системи: змінні середовища, параметри LLM, тюнинг під reasoning-моделі, типові проблеми та як їх розвʼязувати.

## Що де конфігурується

Все runtime — це frozen dataclass [`AppConfig`](../../src/config.py), який читається з env-змінних через [`AppConfig.from_env()`](../../src/config.py). Валідація одразу у `__post_init__` — некоректні значення впасуть на старті, не у середині pipeline-у.

## Змінні середовища

### LLM-провайдер

| Змінна | Дефолт | Опис |
|--------|--------|------|
| `LLM_PROVIDER` | `""` (auto) | `gemini` / `mock`. Порожнє = auto: Gemini якщо є API-key, інакше Mock. |
| `GEMINI_API_KEY` | `""` | Ключ Gemini. Без нього система падає в Mock-режим. |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | Назва моделі (за замовчуванням — найкраща якість для українського вірша; **платна** ~\$2/1M in, ~\$12/1M out). Альтернативи: `gemini-2.5-pro` (трохи дешевша, трохи гірша), `gemini-2.5-flash` (free tier, але якість для поезії помітно гірша). Setup billing: див. [README § Try it in 60 seconds](../../README.md#option-a--full-system-with-real-gemini-recommended). |
| `GEMINI_TEMPERATURE` | `0.9` | `[0, 2]`. Для reasoning знизити до `0.3` зменшує CoT-ліплення у вивід. |
| `GEMINI_MAX_TOKENS` | `8192` | Потрібно ≥ 8192 для reasoning-ів — інакше CoT зʼїдає бюджет і `<POEM>` envelope не встигає вивестись. |
| `GEMINI_DISABLE_THINKING` | `false` | Вмикати **тільки** для моделей що підтримують `ThinkingConfig(thinking_budget=0)` (Gemini 2.5). Pro-preview повертає 400 INVALID_ARGUMENT. |

### LLM-стек надійності

| Змінна | Дефолт | Опис |
|--------|--------|------|
| `LLM_TIMEOUT_SEC` | `120` | Жорсткий дедлайн одного виклику. Для дефолтного `gemini-3.1-pro-preview` 120s акомодує верхню межу легітимного CoT. Якщо переключаєтесь на `gemini-2.5-flash` — знизіть до `20`. |
| `LLM_RETRY_MAX_ATTEMPTS` | `2` | Скільки спроб, включно з першою. `1` вимикає retry. Ретрай на timeout часто марний (модель знову повільна), але страхує від transient 5xx / rate-limit. |

Повний список полів — у [`LLMReliabilityConfig`](../../src/config.py): `timeout_sec`, `retry_max_attempts`, `retry_base_delay_sec` (дефолт `1.0` с), `retry_max_delay_sec` (дефолт `10.0` с), `retry_multiplier` (дефолт `2.0`). Backoff-параметри не винесені в env через малу практичну цінність — за потреби іншої форми retry можна побудувати кастомний `LLMReliabilityConfig` у коді.

### Дані / корпуси

| Змінна | Дефолт | Опис |
|--------|--------|------|
| `CORPUS_PATH` | `corpus/uk_theme_reference_corpus.json` | Тематичний корпус для RAG (semantic retrieval). |
| `METRIC_EXAMPLES_PATH` | `corpus/uk_metric-rhyme_reference_corpus.json` | Метричні приклади. |
| `LABSE_MODEL` | `sentence-transformers/LaBSE` | HuggingFace ID моделі ембеддингів. |
| `OFFLINE_EMBEDDER` | `false` | `true` — детермінований hash-based ембеддер без мережі (тести / CI). |

### Сервер

| Змінна | Дефолт | Опис |
|--------|--------|------|
| `HOST` | `127.0.0.1` | FastAPI bind-адреса. |
| `PORT` | `8000` | Порт. |
| `DEBUG` | `false` | Debug-режим FastAPI. |

## Захист від типових помилок у `.env`

[`AppConfig.from_env`](../../src/config.py) використовує helper `_str(name, default)` який:

- **Стрипає whitespace** з обох кінців.
- **Стрипає inline-коментар** (`"gemini    # provider"` → `"gemini"`). Це захищає від поширеного артефакту `docker-compose`: звичайний `env_file`-парсер **не вирізає** `# comment` після значення, і некоректний рядок у `.env` буде читатися разом з коментарем.

Правило: у `.env` **не пишіть inline-коментарі**. Всі пояснення — на окремому рядку перед змінною. Приклад:

```env
# Empty value = auto (gemini if API key set, else mock).
LLM_PROVIDER=
```

## Поведінка під reasoning-моделлю

Gemini 2.5+ / 3.x Pro **завжди** робить chain-of-thought. Це впливає на все:

1. **`GEMINI_MAX_TOKENS` мусить бути ≥8192.** 4096 замало — CoT обривається до того, як модель дійде до `<POEM>`. У результаті sanitizer видобуває «шматки» з reasoning-а і видає «вірш» з 1-3 рядків.
2. **`LLM_TIMEOUT_SEC` = 120–180.** 60s розраховано на flash-моделі; Pro часом думає до 2 хвилин.
3. **`GEMINI_DISABLE_THINKING=true` НЕ ПРАЦЮЄ для Gemini 3.x Pro preview.** Модель повертає HTTP 400 `"This model only works in thinking mode"`. Залишити `false`.
4. **Temperature 0.3** (замість дефолтного 0.9) зменшує «exploration» і CoT-ліплення, але погіршує різноманіття. Компроміс.

## UI-реакція на повільні виклики

Дві slow-form сторінки (`/generate`, `/evaluate`) мають client-side захист:

- **Спіннер + лічильник часу** на кнопці одразу після submit.
- **Банер «Триває довше ніж очікувалось»** зʼявляється після 60s — на випадок якщо reasoning-модель справді довго думає.
- **Кнопка «Скасувати»** перериває `fetch()` на клієнті через `AbortController`. Сервер **продовжує** обробляти запит (sync handler + threadpool), але користувач може піти й не чекати результат. Токени витратяться, response впаде в nowhere.

Fast-формы (`/validate`, `/detect`) не мають Cancel — нативний submit з затриманим показом спіннера.

Повна логіка — [`main.js`](../../src/handlers/web/static/main.js).

## Ключові алгоритмічні пороги

Це не env-vars, а константи у коді. Змінюються при редагуванні `ValidationConfig` / `DetectionConfig`:

| Параметр | Файл | Опис |
|----------|------|------|
| `RHYME_THRESHOLD` | `ValidationConfig` | Мінімальна similarity для пари щоб рахуватися римою. `0.5` дефолт. |
| `CLAUSULA_MAX_CONSONANT_EDITS` | `ValidationConfig` | Допустимі правки приголосних у клаузулі. |
| `STANZA_SAMPLE_LINES` | `DetectionConfig` | Скільки рядків брати з поеми у brute-force detection. |
| `FEET_MIN_MAX` | `DetectionConfig` | Діапазон перебору foot_count. |
| `_MIN_CYR_LETTERS` / `_MIN_CYR_LETTERS_PUNCT` | `aggregates.py` | Мінімум кирилічних літер для валідного рядка (з/без пунктуації). |

## Docker + env_file

[`docker-compose.yml`](../../docker/docker-compose.yml) робить `env_file: ../.env`. Це означає:

- **Тест у контейнері читає `.env` з хоста.** Якщо там є зламаний рядок — усі тести впадуть на `AppConfig()`.
- **`.env` не в git-і** (gitignore). Синхронізувати зі свіжими env-vars треба вручну з [.env.example](../../.env.example).
- **Inline-коментарі в `.env`** ламають docker-compose env_file. `_str()` helper-а в config.py рятує, але краще не провокувати.

## Маппінг HTTP-помилок

Поверхня API перетворює підкласи `DomainError` у HTTP-відповіді через [`DefaultHttpErrorMapper`](../../src/infrastructure/http/error_mapper.py). Сам mapper — це двохстрочкова перевірка: кожен підклас `DomainError` оголошує власні `http_status_code` і `http_error_type` (див. [`src/domain/errors.py`](../../src/domain/errors.py)), а mapper лише читає ці поля. Додавання нового типу помилки **не вимагає** правки mapper-а.

| Помилка домену | HTTP-статус | Звідки приходить |
|----------------|-------------|------------------|
| `UnsupportedConfigError` | 422 | Caller просить комбінацію метру/схеми, яку система не підтримує |
| `ConfigurationError` | 400 | Некоректні значення `AppConfig` / `ValidationConfig` |
| `ValidationError` | 422 | Вірш/рядок не пройшов валідацію способом, який caller має обробити |
| `RepositoryError` | 503 | I/O-збій у `IThemeRepository` / `IMetricRepository` |
| `EmbedderError` | 503 | Збій кодування в `IEmbedder` |
| `StressDictionaryError` | 503 | Бекенд `IStressDictionary` недоступний |
| `LLMError` | 502 | Усе, що випливає зі стеку декораторів — Gemini-збої, timeout-и, порожній вивід після санітизації, вичерпані retry |
| `DomainError` (root) | 500 | Неочікуваний доменний збій |
| Будь-що інше | 500 | Останній fallback (`InternalServerError`) |

Контракт перевіряється у `tests/unit/infrastructure/http/test_error_mapper.py`.

## Абстракція часу: `IClock` і `IDelayer`

Сервіси ніколи не читають wall clock і не викликають `time.sleep` напряму. Вони залежать від двох портів з [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py): `IClock.now()` для монотонного elapsed-часу і `IDelayer.sleep(seconds)` для cooperative-throttling. Production-адаптери (`SystemClock` / `SystemDelayer`) загортають `time.perf_counter` / `time.sleep`; тести інжектують `FakeClock` / `FakeDelayer`. `RetryingLLMProvider` використовує окремий ін'єктований параметр `sleep_fn` з тієї самої причини — час backoff-у залишається спостережним у тестах без реального очікування.

## Типові сценарії проблем

| Симптом | Швидкий діагноз                                         | Фікс |
|---------|---------------------------------------------------------|------|
| `ConfigurationError: Unknown llm_provider ...` при запуску | Зламаний рядок у `.env`                                 | Приберіть inline-коментар з того рядка |
| `Gemini call failed: 400 INVALID_ARGUMENT. {'message': 'Budget 0 is invalid...'}` | Модель не підтримує `thinking_budget=0`                 | `GEMINI_DISABLE_THINKING=false` |
| `LLM regenerate_lines exceeded timeout of 60.0s` | Дефолт старого flash, reasoning не встиг                | `LLM_TIMEOUT_SEC=180` |
| Ітерація 0 показує лише 1 рядок замість 4 | CoT обрубує вивід до `<POEM>`                           | `GEMINI_MAX_TOKENS=12288` або вище |
| `LLM produced no valid poem lines after sanitization` (після N retry) | Модель видає тільки CoT, ніколи не fact-checks          | Знизити `GEMINI_TEMPERATURE` до `0.3` + підняти max_tokens |
| Spinner крутиться, нічого не відбувається | Weights LaBSE довантажуються на першому виклику (~2 ГБ) | Почекайте перший виклик, далі кеш |

## Див. також

- [llm_decorator_stack.md](./llm_decorator_stack.md) — повна архітектура рішень по надійності.
- [sanitization_pipeline.md](./sanitization_pipeline.md) — що робити коли вивід все одно сміттєвий.
- [feedback_loop.md](./feedback_loop.md) — як timeout / retry взаємодіють з feedback-циклом.
- [.env.example](../../.env.example) — актуальний шаблон конфігу.
