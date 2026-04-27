# Ukrainian Poetry Generation System — Детальний опис

> **Для кого цей документ:** розробники, дослідники, рецензенти, які хочуть зрозуміти, як система працює під капотом — від вхідного запиту до фінального вірша і метрик якості.

> **Англомовна версія:** [`../en/system_overview.md`](../en/system_overview.md).
>
> **Супутні документи** (сусідні файли в цій же теці):
> - Почніть звідси: [огляд для читача](./system_overview_for_readers.md) ([EN](../en/system_overview_for_readers.md))
> - Алгоритми: [наголос і склади](./stress_and_syllables.md), [валідація метру](./meter_validation.md), [валідація рими](./rhyme_validation.md), [детекція](./detection_algorithm.md)
> - RAG і промпти: [семантичний пошук](./semantic_retrieval.md), [побудова промптів](./prompt_construction.md)
> - Цикл корекції: [feedback loop](./feedback_loop.md), [санітизація](./sanitization_pipeline.md), [LLM decorator stack](./llm_decorator_stack.md), [конфігурація](./reliability_and_config.md)
> - Дослідження: [evaluation harness](./evaluation_harness.md) — 18 сценаріїв × 5 абляцій

---

## Зміст

0. [Архітектурні рішення та патерни (OOP/SOLID/DDD)](#0-архітектурні-рішення-та-патерни-oopsolidddd)
1. [Загальна архітектура](#1-загальна-архітектура)
2. [Компонент 1 — Корпус і завантаження даних](#2-компонент-1--корпус-і-завантаження-даних)
3. [Компонент 2 — Семантичний ретрівер (LaBSE)](#3-компонент-2--семантичний-ретрівер-labse)
4. [Компонент 3 — Метричний ретрівер прикладів](#4-компонент-3--метричний-ретрівер-прикладів)
5. [Компонент 4 — Побудова промпту (RAG)](#5-компонент-4--побудова-промпту-rag)
6. [Компонент 5 — LLM-клієнт (Gemini)](#6-компонент-5--llm-клієнт-gemini)
7. [Компонент 6 — Наголосовий словник (UkrainianStressDict)](#7-компонент-6--наголосовий-словник-ukrainianstressdict)
8. [Компонент 7 — Валідатор метру](#8-компонент-7--валідатор-метру)
9. [Компонент 8 — Валідатор рими](#9-компонент-8--валідатор-рими)
10. [Цикл генерації та перегенерації (Feedback Loop)](#10-цикл-генерації-та-перегенерації-feedback-loop)
11. [Метрики якості — формули і обґрунтування](#11-метрики-якості--формули-і-обґрунтування)
12. [Evaluation Harness і абляційні конфігурації](#12-evaluation-harness-і-абляційні-конфігурації)
13. [Сценарії тестування](#13-сценарії-тестування)
14. [Трасування пайплайну (PipelineTrace)](#14-трасування-пайплайну-pipelinetrace)
15. [Змінні середовища і налаштування](#15-змінні-середовища-і-налаштування)
16. [Діаграма потоку даних](#16-діаграма-потоку-даних)

---

## 0. Архітектурні рішення та патерни (OOP/SOLID/DDD)

Система побудована відповідно до принципів **Domain-Driven Design (DDD)**, **SOLID** та класичних патернів проєктування.

### Структура шарів

```
src/
├── domain/              ← Доменний шар (value objects, entities, aggregates, ports)
│   ├── models/          ← MeterSpec, RhymeScheme, Poem, GenerationRequest,
│   │                      LineFeedback, PairFeedback, CorpusEntry, MetricCorpusEntry, ...
│   ├── ports/           ← 30+ абстрактних інтерфейсів (ILLMProvider, IMeterValidator,
│   │                      IClock, IDelayer, IStressPatternAnalyzer, ...)
│   ├── values.py        ← MeterName, RhymePattern enums
│   ├── errors.py        ← DomainError hierarchy (кожен підклас несе власний http_status_code)
│   └── evaluation.py    ← AblationConfig, PipelineTrace
├── services/            ← Шар застосунку (PoetryService, EvaluationService,
│                          BatchEvaluationService, DetectionService)
├── infrastructure/      ← Конкретні реалізації портів
│   ├── composition/     ← DI sub-containers (primitives, validation, generation,
│   │                      metrics, evaluation, detection — кожен розбито на фокусовані файли)
│   ├── clock/           ← SystemClock / SystemDelayer (адаптери IClock / IDelayer)
│   ├── llm/             ← GeminiProvider, MockLLMProvider, decorator stack (5 шарів)
│   ├── http/            ← DefaultHttpErrorMapper (поліморфний dispatch на DomainError)
│   ├── sanitization/    ← SentinelPoemExtractor, RegexPoemOutputSanitizer
│   ├── validators/      ← Meter (Pattern), Rhyme (Phonetic), Composite
│   ├── stages/          ← Pipeline stages
│   ├── pipeline/        ← SequentialPipeline, StageFactory
│   ├── reporting/       ← MarkdownReporter façade + TableFormatter / TraceFormatter
│   │                      / CostCalculator / MarkdownDocumentBuilder колаборатори
│   ├── tracing/         ← PipelineTracer, InMemoryLLMCallRecorder (для UI-трасування)
│   └── ...              ← embeddings, retrieval, repositories, prompts, metrics, ...
├── handlers/            ← Transport adapters (FastAPI, Web UI)
├── runners/             ← IRunner implementations for scripts
├── shared/              ← Cross-cutting pure utilities
├── config.py            ← AppConfig (frozen, from env vars)
└── composition_root.py  ← Тонкий Container façade, що композує sub-контейнери
```

### Доменна модель

**Value Objects** (незмінні, ідентифікуються за значенням):

| Клас | Файл | Призначення |
|------|------|-------------|
| `MeterSpec` | `domain/models/specifications.py` | Метр + кількість стоп |
| `RhymeScheme` | `domain/models/specifications.py` | Схема рими (ABAB, AABB, …) |
| `PoemStructure` | `domain/models/specifications.py` | Кількість строф × рядків |
| `Poem` | `domain/models/aggregates.py` | Parsed poem aggregate |

**Commands / DTOs** (об'єкти передачі даних між шарами):

| Клас | Файл | Призначення |
|------|------|-------------|
| `GenerationRequest` | `domain/models/commands.py` | Повний вхідний запит на генерацію |
| `ValidationRequest` | `domain/models/commands.py` | Запит на валідацію |
| `ValidationResult` | `domain/models/results.py` | Результат валідації метру + рими |
| `GenerationResult` | `domain/models/results.py` | Фінальний результат: вірш + валідація |

`GenerationRequest` замінює довгий список параметрів. Замість десятків аргументів у функції:
```python
service.generate(request)  # один об'єкт GenerationRequest
```

**Абстрактні порти** (`domain/ports/`) — інтерфейси для інфраструктурного шару:

| Інтерфейс | Конкретна реалізація |
|-----------|---------------------|
| `IThemeRepository` | `JsonThemeRepository`, `DemoThemeRepository` |
| `IMetricRepository` | `JsonMetricRepository` |
| `IRetriever` | `SemanticRetriever` (LaBSE cosine similarity) |
| `IPromptBuilder` | `RagPromptBuilder` |
| `IRegenerationPromptBuilder` | `NumberedLinesRegenerationPromptBuilder` |
| `IMeterValidator` | `PatternMeterValidator` |
| `IRhymeValidator` | `PhoneticRhymeValidator` |
| `IPoemValidator` | `CompositePoemValidator` (meter + rhyme) |
| `ILLMProvider` | `GeminiProvider`, `MockLLMProvider` + decorator stack (Logging → Retry → Timeout → Sanitizing → Extracting) |
| `IPoemExtractor` | `SentinelPoemExtractor` (видобуток `<POEM>…</POEM>`) |
| `IPoemOutputSanitizer` | `RegexPoemOutputSanitizer` (allowlist-санітизація) |
| `ILLMCallRecorder` | `InMemoryLLMCallRecorder` (raw/extracted/sanitized для UI-трасування) |
| `IEmbedder` | `LaBSEEmbedder`, `OfflineDeterministicEmbedder`, `CompositeEmbedder` |
| `IStressDictionary` | `UkrainianStressDict` |
| `IPhoneticTranscriber` | `UkrainianIpaTranscriber` |
| `IClock` / `IDelayer` | `SystemClock` / `SystemDelayer` (реальний час), `FakeClock` / `FakeDelayer` (тести) |
| `IHttpErrorMapper` | `DefaultHttpErrorMapper` (поліморфний dispatch за `DomainError.http_status_code`) |

### Патерни проєктування

| Патерн | Де застосований |
|--------|----------------|
| **Strategy** | `IMeterValidator` (Pattern), `IRhymeValidator`, `IStageSkipPolicy` |
| **Repository** | `IThemeRepository`, `IMetricRepository` |
| **Factory** | `ILLMProviderFactory`, `IStageFactory`, `ITracerFactory` |
| **Dependency Injection** | Constructor injection; `composition_root.Container` |
| **Decorator** | LLM reliability + чистка виходу: `Logging → Retry → Timeout → Sanitizing → Extracting` |
| **Composite** | `CompositeEmbedder` (primary + fallback), `CompositePoemValidator` (meter + rhyme) |
| **Null Object** | `NullTracer`, `NullLogger` |
| **Registry** | `IMetricCalculatorRegistry`, `IScenarioRegistry` |

### Принципи SOLID

- **S** (SRP): `PoetryService` оркеструє; `CompositePoemValidator` валідує; `RagPromptBuilder` будує промпт; кожен sub-container wires один шматок графу. `MarkdownReporter` тепер тонкий façade над чотирма колабораторами (`TableFormatter`, `TraceFormatter`, `CostCalculator`, `MarkdownDocumentBuilder`) — кожен фрагмент звітності живе в окремому класі.
- **O** (OCP): нова стратегія валідації чи ретрівера підключається через інтерфейс без зміни пайплайну. `DefaultHttpErrorMapper` додає нові мапінги domain-error → HTTP виключно через розширення — кожен підклас `DomainError` несе власний `http_status_code` і `http_error_type` (ім'я класу), тому ланцюг `isinstance` у мапері відсутній.
- **L** (LSP): контрактні тести (`tests/contracts/`) гарантують взаємозамінність реалізацій — включно з кожним декоратором LLM і повним стеком (див. `tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py`).
- **I** (ISP): 30+ вузьких інтерфейсів замість кількох широких (окремі `ILineSplitter`, `ITokenizer`, `IStringSimilarity`; широкий `IProsodyAnalyzer` тепер deprecated на користь `IStressPatternAnalyzer` + `IExpectedMeterBuilder` + `IMismatchTolerance`).
- **D** (DIP): сервіси залежать лише від абстракцій (`domain/ports/`); конкретні класи wired у `composition_root.py`. Час і sleep абстраговано за `IClock` / `IDelayer`, тому `EvaluationService` та `BatchEvaluationService` ніколи не викликають `time.perf_counter` чи `time.sleep` напряму — у тестах інжектуються `FakeClock` / `FakeDelayer`.

---

## 1. Загальна архітектура

Система є **RAG-пайплайном** (Retrieval-Augmented Generation) для генерації україномовної поезії із заданими просодичними параметрами. Вона складається з п'яти послідовних етапів:

```
Вхід: GenerationRequest (тема, MeterSpec, RhymeScheme, PoemStructure, max_iterations)
        │
        ▼
┌────────────────┐
│ 1. Retrieval   │  ← SemanticRetriever шукає семантично близькі вірші (LaBSE)
│    Stage       │     corpus/uk_theme_reference_corpus.json, 768-dim vectors
└────────────────┘
        │  top-k ThemeExcerpt (тематичне натхнення)
        ▼
┌────────────────┐
│ 2. Metric      │  ← JsonMetricRepository знаходить еталонні вірші
│ Examples Stage │     corpus/uk_metric-rhyme_reference_corpus.json
└────────────────┘
        │  top-k MetricExample (ритмічний еталон)
        ▼
┌────────────────┐
│ 3. Prompt      │  ← RagPromptBuilder будує структурований промпт:
│    Stage       │     тематичні приклади + метричні еталони + параметри форми
└────────────────┘
        │  prompt string
        ▼
┌────────────────┐
│ 4. Generation  │  ← GeminiProvider через 5-шаровий decorator-стек (Logging →
│    Stage       │     Retry → Timeout → Sanitizing → Extracting → Gemini)
│    Stage       │
└────────────────┘
        │  poem text
        ▼
┌────────────────┐
│ 5. Validation  │  ← CompositePoemValidator перевіряє метр (PatternMeterValidator) і
│    Stage       │     риму (PhoneticRhymeValidator) по складах/наголосах
└────────────────┘
        │  ok? → повернути вірш
        │  violations? → сформувати feedback
        ▼
┌────────────────┐
│ 6. Feedback    │  ← ValidatingFeedbackIterator: перегенерація проблемних рядків
│ Loop Stage     │     (до max_iterations разів, зупинка при valid або limit)
└────────────────┘
        │
        ▼
Вихід: GenerationResult(poem, ValidationResult(meter, rhyme, iterations))
```

**Ключова ідея:** LLM не знає правил просодії в явному вигляді. Система компенсує це **символьною перевіркою** після генерації і **цільовим feedback** з точними позиціями помилок. Це робить підхід розширюваним: правила кодуються в `validator.py`, а не у промпті.

---

## 2. Компонент 1 — Корпус і завантаження даних

**Файли:** `src/infrastructure/repositories/theme_repository.py`, `src/domain/models/corpus_entry.py`

### Структура `CorpusEntry`

```python
class CorpusEntry(TypedDict, total=False):
    id: str                          # унікальний ідентифікатор
    text: str                        # повний текст вірша
    author: str                      # автор
    approx_theme: list[str]          # теги теми
    source: str                      # джерело
    lines: int                       # кількість рядків
    title: str                       # назва вірша
    path: str                        # шлях до файлу-джерела
    embedding: list[float]           # попередньо обчислений LaBSE-вектор (768-dim, опціонально)
```

### Джерела корпусу

| Клас / Функція | Джерело | Опис |
|---|---|---|
| `JsonThemeRepository` | `CORPUS_PATH` env → за замовчуванням `corpus/uk_theme_reference_corpus.json` | Тематичний корпус (153 вірші) + LaBSE embeddings |
| `DemoThemeRepository` | хардкодні вірші в коді | fallback, якщо файл не знайдено |
| `JsonMetricRepository` | `METRIC_EXAMPLES_PATH` env → `corpus/uk_metric-rhyme_reference_corpus.json` | Метрично-римні еталони (38 верифікованих записів) |

### Завантаження корпусу

Тематичний корпус завантажується через `JsonThemeRepository` (реалізує `IThemeRepository`), який читає JSON-файл за шляхом з `AppConfig.corpus_path` (за замовчуванням `corpus/uk_theme_reference_corpus.json`). Якщо файл не знайдено, `DemoThemeRepository` повертає хардкодний fallback-корпус.

**Навіщо це потрібно:** корпус слугує базою знань для RAG. Без реальних прикладів поетичних текстів LLM генерує без прив'язки до стилю.

### Поле `embedding` у JSON

Кожен вірш у `uk_theme_reference_corpus.json` має **передобчислений 768-мірний LaBSE-вектор**. Retriever використовує його напряму **без повторного кодування** при кожному запиті — це повністю усуває runtime-overhead на кодування корпусу.

Ембедінги обчислені та записані скриптом:

```bash
# Один крок: побудова тематичного корпусу + ембедінги
make build-theme-corpus-with-embeddings

# Або лише ембедінги для існуючого корпусу (ідемпотентний — пропускає вірші з вже наявними векторами)
make embed-theme-corpus
# python3 scripts/build_corpus_embeddings.py --corpus corpus/uk_theme_reference_corpus.json
```

---

## 3. Компонент 2 — Семантичний ретрівер (LaBSE)

**Файл:** `src/infrastructure/retrieval/semantic_retriever.py` (реалізує `IRetriever`)
**Ембедер:** `src/infrastructure/embeddings/labse.py` → `LaBSEEmbedder` (реалізує `IEmbedder`)
**Стейдж:** `src/infrastructure/stages/retrieval_stage.py` → `RetrievalStage`

### Навіщо потрібен ретрівер

Мета — знайти у корпусі вірші, які **семантично близькі до теми запиту**, щоб подати їх LLM як тематичне натхнення. Це класичний RAG-підхід: замість того щоб LLM покладався тільки на параметри, він бачить конкретні приклади.

### Що таке LaBSE

**LaBSE** (Language-agnostic BERT Sentence Embeddings, Google, 2020) — трансформерна модель (~1.8 GB) для побудови мовно-незалежних векторних представлень речень.

**Архітектура:**
- Base: 12-шаровий BERT-трансформер
- Тренування на двох задачах одночасно:
  1. **MLM** (Masked Language Model) — стандартне BERT-тренування, дає розуміння мови
  2. **TLM** (Translation Language Model) — тренування на 6+ млрд паралельних перекладів для 109 мов, дає крос-мовну сумісність

**Вихід:** 768-мірний вектор на одиничній сфері (після L2-нормалізації). Два речення зі схожим змістом — навіть різними мовами — матимуть вектори з **великим косинусним добутком** (близькими до 1.0). Не пов'язані тексти — близько до 0 або від'ємні.

**Чому LaBSE, а не інші моделі:**
- Натренована саме на **sentence-level similarity**, не на token-level
- Добре підтримує українську (кирилиця входить у словник WordPiece)
- Вектори геометрично осмислені: близькість = схожість за змістом

### Алгоритм `retrieve()`

```
1. encode(theme_description)  →  theme_vec  [768 float]
        ↓
2. Для кожного вірша в корпусі:
   а) беремо poem.embedding (pre-computed, завжди присутній)  →  poem_vec
   б) якщо embedding відсутній (старий корпус) → encode(poem.text) on-the-fly
   в) cosine_similarity(theme_vec, poem_vec)
        ↓
3. Сортуємо за спаданням similarity
        ↓
4. Повертаємо top_k (за замовчуванням 5) найближчих
```

Для поточного `uk_theme_reference_corpus.json` крок 2б **ніколи не виконується** — всі 153 вірші мають передобчислені вектори.

### Обчислення косинусної схожості

```python
dot  = sum(a * b for a, b in zip(theme_vec, poem_vec))
norm_a = sqrt(sum(a*a for a in theme_vec))
norm_b = sqrt(sum(b*b for b in poem_vec))
sim = dot / (norm_a * norm_b)   # ∈ [-1, 1]
```

Оскільки вектори L2-нормовані (`normalize_embeddings=True`), `norm_a = norm_b = 1`, тому `sim = dot` — просто скалярний добуток.

### Fallback без LaBSE — `OfflineDeterministicEmbedder`

**Файл:** `src/infrastructure/embeddings/offline.py`

Якщо модель не завантажилась або `OFFLINE_EMBEDDER=true`:

```python
# Детермінований псевдовипадковий вектор на основі хешу тексту
rng = random.Random(abs(hash(text)) % (2**32))
return [rng.gauss(0.0, 1.0) for _ in range(768)]
```

Один і той самий текст завжди дає один вектор, але **семантичного сенсу немає** — це тільки для тестів без API.

`CompositeEmbedder` (`src/infrastructure/embeddings/composite.py`) реалізує Composite Pattern: пробує primary (`LaBSEEmbedder`), а при помилці — fallback (`OfflineDeterministicEmbedder`).

---

## 4. Компонент 3 — Метричний ретрівер прикладів

**Файл:** `src/infrastructure/repositories/metric_repository.py` (реалізує `IMetricRepository`)
**Модель:** `src/domain/models/entities.py` → `MetricExample`
**Стейдж:** `src/infrastructure/stages/metric_examples_stage.py` → `MetricExamplesStage`

### Навіщо потрібен

Семантичний ретрівер знаходить тематично близькі вірші, але не гарантує що вони мають потрібний **метр і схему рими**. Метричний ретрівер вирішує іншу задачу: знайти еталонні вірші, які точно відповідають заданому метру, кількості стоп і схемі рими. Ці приклади додаються в промпт як **ритмічний і рифмований орієнтир** для LLM.

### Структура `MetricExample`

```python
@dataclass(frozen=True)
class MetricExample:
    id: str           # унікальний ідентифікатор (наприклад, "iamb_4_ABAB_shevchenko")
    meter: str        # "ямб", "хорей", "дактиль", "амфібрахій", "анапест"
    feet: int         # кількість стоп
    scheme: str       # "ABAB", "AABB", "ABBA", "AAAA"
    text: str         # повний текст вірша-прикладу
    verified: bool    # True = вручну верифікований еталон
    author: str       # автор
    note: str         # примітки
```

Дані зберігаються у `MetricCorpusEntry` (TypedDict, `src/domain/models/metric_corpus_entry.py`) і перетворюються у `MetricExample` entities при завантаженні.

### Датасет `corpus/uk_metric-rhyme_reference_corpus.json`

Містить вірші-зразки з точною розміткою метру, стоп і схеми рими від класиків:

| Метр | Приклади |
|------|---------|
| ямб | Шевченко "Реве та стогне…" (4ст, ABAB) |
| хорей | Чупринка (4ст, ABAB) |
| дактиль | Сковорода (4ст, AABB) |
| амфібрахій | Сосюра (4ст, ABAB) |
| анапест | Леся Українка, Костенко (3ст, ABAB) |

### Алгоритм `JsonMetricRepository.query()`

```python
class JsonMetricRepository(IMetricRepository):
    def query(self, meter: str, feet: int, scheme: str,
              top_k: int = 3) -> list[MetricExample]:
        # 1. Нормалізація назви метру через MeterCanonicalizer
        #    "iamb" → "ямб", "trochee" → "хорей", ...
        meter_ua = self._canonicalizer.canonicalize(meter)

        # 2. Фільтрація по точному збігу: meter + feet + scheme
        matched = [e for e in self._entries if
                   e.meter.lower() == meter_ua and
                   e.feet == feet and
                   e.scheme.upper() == scheme.upper()]

        # 3. Верифіковані приклади йдуть першими
        matched = sorted(matched, key=lambda e: (not e.verified,))

        return matched[:top_k]
```

**Ключові властивості:**
- Повертає `[]` якщо файл не знайдено (не падає з помилкою)
- Підтримка англійських псевдонімів: `iamb/trochee/dactyl/amphibrach/anapest`
- `verified_only=True` — повертає лише вручну перевірені приклади
- Верифіковані приклади сортуються перед неверифікованими

---

## 5. Компонент 4 — Побудова промпту (RAG)

**Файл:** `src/infrastructure/prompts/rag_prompt_builder.py`
**Порт:** `src/domain/ports/prompts.py` → `IPromptBuilder`

`RagPromptBuilder` реалізує `IPromptBuilder` і будує промпт з тематичних прикладів (від `SemanticRetriever`), метричних еталонів (від `JsonMetricRepository`), і параметрів форми (від `GenerationRequest`). Будується через `PipelineState`:

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

### Структура промпту (з метричними прикладами)

```
Use the following poetic excerpts as thematic inspiration (do not copy):
[вірш 1 з корпусу — семантично близький до теми]
[вірш 2 з корпусу]
...

Use these verified examples as METER and RHYME reference
(they demonstrate ямб meter with ABAB rhyme scheme — follow this rhythm and rhyme pattern exactly):
[верифікований вірш-зразок 1 — Шевченко]
[верифікований вірш-зразок 2]

Theme: весна у лісі, пробудження природи
Meter: ямб
Rhyme scheme: ABAB
Structure: 2 stanzas of 4 lines each (8 lines total)
Generate a Ukrainian poem with exactly 8 lines.
```

**Дві секції з різним призначенням:**
- **Тематичні приклади** (семантичний ретрівер): дають LLM лексику, образи, стиль теми
- **Метричні приклади** (метричний ретрівер): показують LLM точний ритм і схему рими яку треба відтворити

### Параметри структури

`stanza_count` і `lines_per_stanza` беруться безпосередньо з поля `EvaluationScenario` (або перевизначаються через `--stanzas`/`--lines-per-stanza` CLI / Makefile). Добуток `stanza_count × lines_per_stanza` = `total_lines` передається LLM як жорстка вимога.

**Навіщо "do not copy":** без цієї вказівки LLM може буквально відтворити вірш із корпусу. Нас цікавить тематичне натхнення, а не копіювання.

**Системна інструкція** передається окремо через `system_instruction` у `GeminiProvider`:
```
You are a Ukrainian poetry generator. Return only the poem text, no explanations, no markdown.
```

Це дає LLM чіткий контекст ролі і усуває зайвий текст у відповіді (коментарі, пояснення, markdown-форматування).

---

## 6. Компонент 5 — LLM-клієнт (Gemini)

**Файл:** `src/infrastructure/llm/gemini.py`

### Абстракція `ILLMProvider`

```python
class ILLMProvider(ABC):
    def generate(self, prompt: str, max_tokens: int) -> str: ...
```

Єдина операція `generate` — генерує текст за промптом. Перша генерація використовує RAG-промпт, перегенерація — feedback-промпт з описом порушень.

### `GeminiProvider` — реальний провайдер

Використовує **новий `google.genai` SDK** (не deprecated `google.generativeai`):

```python
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-3.1-pro-preview",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.9,          # висока: більше творчості
        max_output_tokens=8192,   # для reasoning-моделей ≥ 8192 обовʼязково
        system_instruction=...,
    ),
)
```

**Параметри (актуальні дефолти):**
- `temperature=0.9` — відносно висока, щоб генерація була варіативною і не повторювала однакові рядки. Для reasoning-моделей (Gemini 2.5+ / 3.x Pro) рекомендовано знижувати до `0.3` — зменшує ліплення CoT у вивід.
- `max_output_tokens=8192` — мусить бути ≥ 8192 на reasoning-моделях, інакше chain-of-thought зʼїдає бюджет до того, як модель виведе `<POEM>` envelope.
- `model="gemini-3.1-pro-preview"` — дефолт. Платна модель, найкраща якість для українського вірша. Альтернативи: `gemini-2.5-pro` (трохи дешевша), `gemini-2.5-flash` (free tier, але якість для поезії помітно гірша).
- `thinking_config` — якщо `GEMINI_DISABLE_THINKING=true`, передається `ThinkingConfig(thinking_budget=0, include_thoughts=False)`. Gemini 2.5 це підтримує, Gemini 3.x Pro preview — ні (повертає HTTP 400).

### `MockLLMProvider` — заглушка для тестів

Повертає фіксований вірш без API-запиту. Це дозволяє тестувати пайплайн без витрат API-квоти.

### Декоратори надійності LLM (повний 5-шаровий стек)

Реальний `GeminiProvider` обгортається стеком декораторів (Decorator Pattern). Порядок зовнішній → внутрішній:

```
LoggingLLMProvider              ← структурний лог на кожний виклик + duration
  └─ RetryingLLMProvider        ← експ. backoff на LLMError (до retry_max_attempts)
      └─ TimeoutLLMProvider     ← жорсткий дедлайн (timeout_sec)
          └─ SanitizingLLMProvider   ← allowlist-санітизація, порожнє → LLMError
              └─ ExtractingLLMProvider ← видобуток <POEM>…</POEM> з envelope
                  └─ GeminiProvider   ← реальний виклик Gemini API
```

- **`LoggingLLMProvider`** — структурний INFO/ERROR лог, бачить оригінальні аргументи і фінальний результат (після retry).
- **`RetryingLLMProvider`** — повторна спроба на `LLMError`. Таймаут теж вважається `LLMError`, тому ретраїться (часто марно — модель знову стільки ж).
- **`TimeoutLLMProvider`** — запускає внутрішній виклик у daemon-потоці; на перевищення `timeout_sec` кидає `LLMError`. **Потік не вмирає**, фактичний HTTP-запит до Gemini триває далі; це Python-обмеження.
- **`SanitizingLLMProvider`** — прогонює вихід через `IPoemOutputSanitizer`. На порожньому результаті (все сміття) кидає `LLMError`, що дає retry-шару шанс спробувати ще раз. Пише sanitized-текст у `ILLMCallRecorder` для UI-трасування.
- **`ExtractingLLMProvider`** — видобуває вміст між тегами `<POEM>…</POEM>` через `IPoemExtractor`. Без тегів — повертає вхід незміненим (sanitizer підбере). Пише raw + extracted у `ILLMCallRecorder`.

Конфігурація — `LLMReliabilityConfig` у `AppConfig` (див. §15). Санітизатор і екстрактор деталізовано у [`sanitization_pipeline.md`](./sanitization_pipeline.md); декоратори — у [`llm_decorator_stack.md`](./llm_decorator_stack.md).

### Санітизація виводу LLM

Reasoning-моделі часто «просочують» chain-of-thought у фінальний вивід: scansion-нотацію (`КрОки`, `(u u -)`), склади з дефісами (`за-гу-бив-ся`), англомовні коментарі, bullet-марковані пояснення. Система має двошаровий захист:

1. **Sentinel extraction** — модель просять загорнути фінальний вірш у `<POEM>…</POEM>` теги. `SentinelPoemExtractor` ([`src/infrastructure/sanitization/sentinel_poem_extractor.py`](../../src/infrastructure/sanitization/sentinel_poem_extractor.py)) толерантний до збоїв: кілька блоків → береться останній (як правило, фінальна редакція після CoT); тільки відкритий тег без закриваючого → береться все після останнього `<POEM>` (`max_tokens`-обрубаний вивід); відсутність тегів → вхід проходить далі на sanitizer.

2. **Allowlist-санітизація** — `RegexPoemOutputSanitizer` ([`src/infrastructure/sanitization/regex_poem_output_sanitizer.py`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py)) перевіряє кожен рядок посимвольно: дозволені **тільки** українські кириличні літери, комбінований акут, апостроф, пунктуація (. , ! ? : ; …), тире / дефіс, лапки (« » „ " " " '), круглі дужки, пробіл. Усе інше (латиниця, цифри, `|`, `/`, `\`, `<>`, `[]`, `=`, emoji) автоматично дискваліфікує рядок. Додатково три behavioural-перевірки: мінімум одна кирилична літера; заборона lowercase→uppercase у токені (`КрО`); заборона ≥2 intraword-дефісів (`за-гу-бив-ся`).

Детальне пояснення алгоритму + «salvage pass» для парен-блоків зі scansion — у [`sanitization_pipeline.md`](./sanitization_pipeline.md).

### LLM call tracing

Для відображення у UI (сторінки генерації + оцінки абляцій) обидва sanitization-декоратори пишуть у `ILLMCallRecorder` ([`src/domain/ports/llm_trace.py`](../../src/domain/ports/llm_trace.py), реалізація `InMemoryLLMCallRecorder` у [`src/infrastructure/tracing/llm_call_recorder.py`](../../src/infrastructure/tracing/llm_call_recorder.py)):

- `record_raw(text)` — оригінальна відповідь Gemini (ExtractingLLMProvider на вході)
- `record_extracted(text)` — текст після видобутку `<POEM>…</POEM>` (ExtractingLLMProvider на виході)
- `record_sanitized(text)` — текст після allowlist-фільтра (SanitizingLLMProvider на виході)

`ValidationStage` (ітерація 0) і `ValidatingFeedbackIterator` (ітерації 1+) читають snapshot рекордера і зберігають у `IterationRecord.raw_llm_response` / `.sanitized_llm_response`. UI рендерить обидва поля під collapsible-блоком «LLM trace (raw / sanitized)».

### Вибір LLM-провайдера

`ILLMProviderFactory` (конкретна реалізація: `DefaultLLMProviderFactory`) автоматично обирає провайдера:
- Якщо `GEMINI_API_KEY` задано → `GeminiProvider` (з повним 5-шаровим decorator-стеком)
- Якщо ключа немає → `MockLLMProvider` (детерміністична заглушка)

Вибір відбувається через `composition_root.py` при побудові контейнера залежностей. `GenerationSubContainer` тепер тонкий façade, що композує три фокусовані sub-контейнери — `GenerationDataPlaneSubContainer` (репозиторії, ембедер, ретрівер), `LLMStackSubContainer` (фабрика + декоратори надійності) і `PipelineStagesSubContainer` (промпти, feedback loop, pipeline) — кожен у власному модулі під `src/infrastructure/composition/`.

---

## 7. Компонент 6 — Наголосовий словник (UkrainianStressDict)

**Файл:** `src/infrastructure/stress/ukrainian.py`, порт: `src/domain/ports/stress.py`

### Навіщо він потрібен

Щоб перевірити метр вірша, потрібно знати **на який склад падає наголос у кожному слові**. В українській мові наголос вільний (немає фіксованого правила), тому потрібен зовнішній ресурс.

### Реалізація

`UkrainianStressDict` реалізує інтерфейс `IStressDictionary`:

```python
class UkrainianStressDict(IStressDictionary):
    on_ambiguity: str = "first"   # що робити з омографами: "first" / "random"

    def __post_init__(self):
        from ukrainian_word_stress import Stressifier, StressSymbol
        self._stressify = Stressifier(
            stress_symbol=StressSymbol.CombiningAcuteAccent,
            on_ambiguity=self.on_ambiguity,
        )
```

Бібліотека `ukrainian-word-stress` використовує **Stanza NLP** (Stanford NLP Group) для морфологічного аналізу, який при першому запуску завантажує ~500 MB моделей.

### Метод `get_stress_index(word) → int | None`

1. Викликає `self._stressify(word)` → повертає слово з Unicode-символом наголосу `\u0301` після наголошеної голосної
2. Проходить по символах, рахує голосні, знаходить де стоїть `\u0301` → повертає **0-based індекс наголошеної голосної** серед усіх голосних слова

**Приклад:** `"лі́с"` → наголос на 0-й голосній → `index = 0`; `"весна́"` → на 1-й → `index = 1`

### Fallback — `PenultimateFallbackStressResolver`

**Файл:** `src/infrastructure/stress/penultimate_resolver.py`

Реалізує `IStressResolver`. Якщо `UkrainianStressDict` не може визначити наголос (слово не розпізнане) — fallback **ставить наголос на передостанній склад** (пенультима — найчастіша позиція наголосу в українській мові).

### Підрахунок складів — `SyllableCounter`

**Файл:** `src/infrastructure/stress/syllable_counter.py`

Реалізує `ISyllableCounter`. Рахує голосні в слові для визначення кількості складів.

---

## 8. Компонент 7 — Валідатор метру

**Файли:** `src/infrastructure/validators/meter/pattern_validator.py`
**Порт:** `src/domain/ports/validation.py` → `IMeterValidator`

### Підтримувані метри

**Файл шаблонів:** `src/infrastructure/meter/ukrainian_meter_templates.py` (реалізує `IMeterTemplateProvider`)

```python
METER_TEMPLATES = {
    "ямб":        ["u", "—"],       # нАголос на парній складі
    "хорей":      ["—", "u"],       # нАголос на непарній
    "дактиль":    ["—", "u", "u"],  # трискладова стопа
    "амфібрахій": ["u", "—", "u"],
    "анапест":    ["u", "u", "—"],
}
```

`"—"` = наголошена позиція, `"u"` = ненаголошена.

**Канонізація назв метрів:** `MeterCanonicalizer` (`src/infrastructure/meter/meter_canonicalizer.py`) нормалізує англійські та українські псевдоніми: `"iamb"` → `"ямб"`, `"trochee"` → `"хорей"`, тощо.

### Алгоритм валідації рядка (`PatternMeterValidator`)

**Крок 1 — Токенізація рядка:**
```python
tokens = tokenize_line_ua(line)
# → LineTokens(words=["весна", "прийшла", ...], syllables_per_word=[2, 3, ...])
```
`tokenize_line_ua` витягує слова через regex `[а-яіїєґʼ'-]+`, рахує голосні у кожному слові.

**Крок 2 — Очікуваний паттерн:**
```python
expected = build_expected_pattern("ямб", foot_count=4)
# → ["u","—","u","—","u","—","u","—"]  (4 стопи × 2 символи = 8 позицій)
```

**Крок 3 — Реальний паттерн наголосів:**
Для кожного слова: знаходимо наголос через `UkrainianStressDict` (реалізація `IStressDictionary`), ставимо `"—"` на відповідну позицію у загальному масиві складів, решта — `"u"`.

```
"Весна  прийшла  у  ліс  зелений"
  2сл    3сл    1сл 1сл    3сл      ← syllables_per_word
  [u,—]  [u,—,u] [u] [—]  [u,—,u]  ← actual stress positions
→ actual = [u,—, u,—,u, u, —, u,—,u]
```

**Крок 4 — Толерантне порівняння з підтримкою ритмічних замін:**

```python
n = min(len(actual), len(expected))
raw_errors = [i + 1 for i in range(n) if actual[i] != expected[i]]

# Фільтруємо дозволені ритмічні заміни
real_errors = [pos for pos in raw_errors
               if not _is_tolerated_mismatch(pos - 1, actual, expected, flags)]

length_ok = _line_length_ok(actual, expected)
ok = len(real_errors) <= allowed_mismatches and length_ok
```

**Дозволені ритмічні відступи:**

| Заміна | Умова толерантності | Пояснення |
|--------|---------------------|-----------|
| **Пірихій** (очікується `—`, є `u`) | односкладове або службове слово | прийменники, сполучники, частки, займенники |
| **Спондей** (очікується `u`, є `—`) | односкладове або службове слово | вторинний наголос природній для таких слів |

**Службові слова** (визначені у `src/infrastructure/meter/ukrainian_weak_stress_lexicon.py`): ~50 слів: прийменники (`в`, `на`, `до`…), сполучники (`і`, `та`, `що`…), частки (`не`, `б`, `же`…), особові займенники (`я`, `ти`, `він`…), присвійні займенники (`мій`, `твій`, `свій`…). Класифікація складів відбувається через `SyllableFlagStrategy` (`src/infrastructure/meter/syllable_flag_strategy.py`).

**Дозволені варіації довжини рядка (`_line_length_ok`):**

| Відхилення | Умова | Назва |
|------------|-------|-------|
| `+1` | останній склад `u` | жіноче закінчення |
| `+2` | останні два склади `u u` | дактилічне закінчення |
| `-1 ≤ diff < 0` для 2-складових стоп (ямб, хорей) | безумовно | каталектика |
| `-2 ≤ diff < 0` для 3-складових стоп (дактиль, амфібрахій, анапест) | безумовно | каталектика |

Відхилення `|diff| ≥ foot_size` означає пропущену цілу стопу (напр., 5-стопний ямб замість 6-стопного: `diff=-2` для `foot_size=2`) і **відкидається**.

**Допустиме відхилення `allowed_mismatches=2`:** після фільтрації пірихіїв і спондеїв, рядок вважається **правильним**, якщо реальних (не-толерантних) невідповідностей ≤ 2 і довжина рядка в межах дозволеного.

### Метрика Meter Accuracy

```
meter_accuracy = (кількість рядків з ok=True) / (загальна кількість рядків)
```

Рахується окремо для кожного рядка вірша. Значення `1.0` = всі рядки відповідають метру.

---

## 9. Компонент 8 — Валідатор рими

**Файли:** `src/infrastructure/validators/rhyme/phonetic_validator.py`, `src/infrastructure/validators/rhyme/pair_analyzer.py`, `src/infrastructure/validators/rhyme/scheme_extractor.py`, `src/infrastructure/validators/rhyme/precision_classifier.py`
**Порт:** `src/domain/ports/rhyme.py` → `IRhymeValidator`, `IRhymePairAnalyzer`, `IRhymeSchemeExtractor`
**Фонетика:** `src/infrastructure/phonetics/ukrainian_ipa_transcriber.py` → `IPhoneticTranscriber`

### Схеми рими

```python
"AABB" → пари (0,1), (2,3)       # суміжна рима
"ABAB" → пари (0,2), (1,3)       # перехресна рима
"ABBA" → пари (0,3), (1,2)       # кільцева рима
"AAAA" → всі пари між рядками    # монорима
```

### Алгоритм перевірки рими

**Крок 1 — Знаходимо останнє слово кожного рядка.**

**Крок 2 — Транскрипція в IPA (International Phonetic Alphabet):**

```python
# src/infrastructure/phonetics/ukrainian_ipa_transcriber.py
class UkrainianIpaTranscriber(IPhoneticTranscriber):
    _UA_MAP = {"а":"a", "б":"b", "г":"ɦ", "ж":"ʒ", "и":"ɪ", "і":"i", ...}

    def transcribe(self, word: str) -> str:
        # побуквена заміна через _UA_MAP
        # "зелений" → "zelenjɪj"
```

**Навіщо IPA:** порівнювати кириличний запис некоректно — `"ь"` не є звуком, `"я"` → `"ja"` (два символи). IPA дає **фонетичне представлення**, за яким рима оцінюється коректніше.

**Крок 3 — Rhyme part від наголошеної голосної до кінця:**

```python
def rhyme_part_from_stress(word, stress_syllable_idx_0based) -> str:
    ipa = transcribe_ua(word)
    vpos = vowel_positions_in_ipa(ipa)          # позиції голосних в IPA-рядку
    stress_pos = vpos[stress_syllable_idx_0based]
    return ipa[stress_pos:]                     # від наголошеної голосної до кінця
```

**Приклад:**
```
"зелений" → IPA: "zelenjɪj"
Голосні в IPA: позиції [1 (e), 5 (e), 7 (ɪ)]
Наголос на 2-й голосній (index=1) → позиція 5
rhyme_part = "ɪj"

"натхненні" → IPA: "natxnenjɪ"
Наголос на 2-й голосній → rhyme_part = "i"
```

**Крок 4 — Нормалізована відстань Левенштейна:**

```python
# src/infrastructure/text/levenshtein_similarity.py (реалізує IStringSimilarity)
# + src/shared/string_distance.py (базові алгоритми)
def normalized_similarity(a: str, b: str) -> float:
    d = levenshtein_distance(a, b)
    return 1.0 - d / max(len(a), len(b))
```

Відстань Левенштейна рахує мінімальну кількість операцій (вставка, видалення, заміна) для перетворення `a` в `b`. Нормалізована схожість = `1 - d/max_len` ∈ [0, 1].

**Поріг:** рима вважається **правильною**, якщо `score >= rhyme_threshold` (за замовчуванням `0.55`, конфігурується через `ValidationConfig`).

### Класифікація точності рими (`RhymePrecision`)

**Файл:** `src/infrastructure/validators/rhyme/precision_classifier.py`

| Рівень | Опис |
|--------|------|
| `EXACT` | повний збіг від наголошеної голосної до кінця |
| `ASSONANCE` | збіг голосних, розбіжність приголосних |
| `CONSONANCE` | збіг приголосних, розбіжність голосних |
| `INEXACT` | часткова подібність вище порогу |
| `NONE` | score нижче порогу — рими немає |

### Метрика Rhyme Accuracy

```
rhyme_accuracy = (кількість пар з rhyme_ok=True) / (загальна кількість пар)
```

Для ABAB з 4 рядками — 2 пари: (0,2) і (1,3). Якщо одна пара рима — `0.5`.

---

## 10. Цикл генерації та перегенерації (Feedback Loop)

**Файли:** `src/infrastructure/regeneration/feedback_cycle.py` (ValidationFeedbackCycle), `src/infrastructure/regeneration/validating_feedback_iterator.py` (ValidatingFeedbackIterator), `src/infrastructure/regeneration/iteration_stop_policy.py` (MaxIterationsOrValidStopPolicy), `src/infrastructure/regeneration/line_index_merger.py` (LineIndexMerger)
**Порти:** `src/domain/ports/pipeline.py` → `IFeedbackCycle`, `IFeedbackIterator`, `IIterationStopPolicy`

### Покроковий процес

```
┌───────────────────────────────────────────────────────────────────────┐
│ DefaultPoemGenerationPipeline.build(GenerationRequest)                      │
│  (orchestrated by PoetryService.generate())                                │
└───────────────────────────────────────────────────────────────────────┘
         │
         ▼
[1] RetrievalStage                 → SemanticRetriever.retrieve(theme)
                                     top-5 семантично близьких віршів
                                     (використовує pre-computed LaBSE embeddings)
[2] MetricExamplesStage            → JsonMetricRepository.query(meter, feet, scheme)
                                     top-2 верифікованих вірші-зразки
                                     точно за метром, стопами і схемою рими
[3] PromptStage                    → RagPromptBuilder.build(state)
                                     зібрати промпт з тематичними і метричними
                                     прикладами, stanza_count × lines_per_stanza
[4] GenerationStage                → ILLMProvider.generate(prompt) → Gemini генерує вірш
[5] ValidationStage                → CompositePoemValidator.validate(poem, meter, rhyme)
      IMeterValidator.validate()   → перевірити кожен рядок по складах/наголосах
                                     (з урахуванням пірихіїв, спондеїв, каталектики)
      IRhymeValidator.validate()   → перевірити пари рядків на риму

[6] Якщо meter_ok AND rhyme_ok → ✅ ГОТОВО, повернути вірш

[7] FeedbackLoopStage (якщо є порушення):
    → ValidationFeedbackCycle.generate_feedback() для кожного рядка/пари
    → NumberedLinesRegenerationPromptBuilder.build() — промпт з помилками
    → ILLMProvider.generate(regen_prompt) → Gemini виправляє
    → LineIndexMerger.merge(original, regenerated, feedback)
         ↑ safety guard: якщо LLM повернув < рядків — підставляє оригінал
    → CompositePoemValidator.validate() → re-validate merged poem
    → MaxIterationsOrValidStopPolicy — зупинка якщо valid АБО max_iterations

[8] FinalMetricsStage (тільки в evaluation mode):
    → MeterAccuracy, RhymeAccuracy, SemanticRelevance, IterationMetrics, LineCount

[9] Повернути фінальний вірш + GenerationResult(poem, ValidationResult)
```

### Формат feedback-повідомлень

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

**Чому такий детальний feedback:** LLM не може "відчути" метр. Але якщо точно вказати **яка позиція наголосу неправильна** і **яке закінчення рими очікується в IPA**, у моделі є достатньо інформації для цільового виправлення конкретного рядка без переписування всього вірша.

### Параметр `max_iterations`

| Значення | Поведінка |
|---|---|
| `0` | лише генерація, без feedback loop |
| `1` (default) | одна спроба виправлення |
| `3+` | кілька спроб, але кожна — окремий API-запит |

За замовчуванням `max_iterations=1` щоб обмежити витрати API. При абляційних дослідженнях можна збільшити через `--max-iterations N`.

### Що повертає `GenerationResult`

```python
@dataclass(frozen=True)
class GenerationResult:
    poem: str                         # фінальний текст вірша
    validation: ValidationResult      # результат валідації метру + рими

@dataclass(frozen=True)
class ValidationResult:
    meter: MeterResult                # ok, accuracy, feedback per line
    rhyme: RhymeResult                # ok, accuracy, feedback per pair
    iterations: int                   # скільки ітерацій feedback loop

@dataclass(frozen=True)
class MeterResult:
    ok: bool                          # всі рядки відповідають метру
    accuracy: float                   # частка правильних рядків [0,1]
    feedback: tuple[LineFeedback, ...]  # помилки по рядках

@dataclass(frozen=True)
class RhymeResult:
    ok: bool                          # всі пари рими правильні
    accuracy: float                   # частка правильних пар рими [0,1]
    feedback: tuple[PairFeedback, ...]  # помилки по парах
```

---

## 11. Метрики якості — формули і обґрунтування

**Файли:** `src/infrastructure/metrics/` (meter_accuracy, rhyme_accuracy, semantic_relevance, regeneration_success, iteration_metrics, line_count, registry)

Усі метрики реалізують порт `IMetricCalculator` і реєструються у `DefaultMetricCalculatorRegistry`. `FinalMetricsStage` прогоняє увесь реєстр наприкінці pipeline-у і складає `context.final_metrics` — ключі рівно такі, як `IMetricCalculator.name`.

**Композиція.** `MetricsSubContainer` сам є тонким façade-ом і композує два фокусовані sub-контейнери: `CalculatorRegistrySubContainer` (реєстр + калькулятори + фінальний stage) та `ReportingSubContainer` (репортер, results-writer-и, tracer factory, HTTP error mapper, evaluation aggregator). Кожен живе у власному модулі під `src/infrastructure/composition/`, тому нова метрика чи новий writer змінюють один фокусований файл, а не широкий metrics-контейнер.

**Реєстр метрик (8 калькуляторів):**

| Ключ | Клас | Файл | Значення | Коли 0 |
|------|------|------|----------|--------|
| `meter_accuracy` | `MeterAccuracyCalculator` | `meter_accuracy.py` | частка рядків, що пройшли метричний валідатор | вірш порожній |
| `rhyme_accuracy` | `RhymeAccuracyCalculator` | `rhyme_accuracy.py` | частка пар, що пройшли фонетичну перевірку | пар нема |
| `semantic_relevance` | `SemanticRelevanceCalculator` | `semantic_relevance.py` | cosine(embed(theme), embed(poem_text)) | `EmbedderError` або пусті тексти |
| `regeneration_success` | `RegenerationSuccessCalculator` | `regeneration_success.py` | дельта середньої accuracy (метр+рима) від перша → остання ітерація | ітерацій < 2 |
| `meter_improvement` | `MeterImprovementCalculator` | `iteration_metrics.py` | `final.meter_accuracy − initial.meter_accuracy` | ітерацій < 2 |
| `rhyme_improvement` | `RhymeImprovementCalculator` | `iteration_metrics.py` | `final.rhyme_accuracy − initial.rhyme_accuracy` | ітерацій < 2 |
| `feedback_iterations` | `FeedbackIterationsCalculator` | `iteration_metrics.py` | кількість ітерацій feedback loop (крім initial) | завжди визначена |
| `num_lines` | `LineCountCalculator` | `line_count.py` | кількість непорожніх рядків у фінальному вірші | порожній вірш |

### 11.1 Meter Accuracy

```
meter_accuracy = Σ(рядок_i.ok) / N_рядків
```

Де `рядок_i.ok = True` якщо кількість **реальних** (не-толерантних) невідповідностей наголосів ≤ `allowed_mismatches=2` **і** довжина рядка допустима (`_line_length_ok`).

**Обґрунтування порогу 2:** класична поезія допускає **ритмічні варіації**. Пірихії і спондеї на службових і односкладових словах не вважаються помилками — вони фільтруються до підрахунку. Строге правило `≤0 mismatches` відкидало б канонічні рядки Шевченка, Лесі Українки, Костенко.

### 11.2 Rhyme Accuracy

```
rhyme_accuracy = Σ(пара_i.rhyme_ok) / N_пар
```

Де `пара_i.rhyme_ok = True` якщо `normalized_similarity(rhyme_part_1, rhyme_part_2) ≥ rhyme_threshold` (за замовчуванням `0.55`, конфігурується через `ValidationConfig`).

**Обґрунтування порогу:** рима не завжди точна (чоловіча/жіноча, тощо). Поріг дозволяє приймати неточні рими і асонанси, але відхиляє суттєві розходження. Конкретне значення підібране експериментально на українському матеріалі.

### 11.3 Semantic Relevance

```python
# src/infrastructure/metrics/semantic_relevance.py
semantic_relevance = cosine(embed(theme), embed(poem_text))
                   = dot(theme_vec, poem_vec) / (||theme_vec|| * ||poem_vec||)
```

Вимірює **семантичну близькість фінального вірша до заданої теми**. Використовує той самий `IEmbedder` (`LaBSEEmbedder` у проді, `OfflineDeterministicEmbedder` у тестах), що і `SemanticRetriever` — це гарантує метрологічну узгодженість із retrieval-фазою.

**Діапазон:** `[-1, 1]` теоретично, практично `[0, 1]` (нормалізовані LaBSE-вектори у семантично валідному просторі майже не дають від'ємних косинусів).

**Значення ≥ 0.6** — тематично дотичний вірш. **≥ 0.8** — високо релевантний. **< 0.4** — модель «втекла» у бічну тему (часто через погано сформульований промпт або занадто малу кількість retrieval-прикладів).

**Поведінка при збоях:**
- `EmbedderError` (LaBSE недоступний, offline fallback не виручив) → повертає `0.0` і пише `warning` у лог. **НЕ** зриває pipeline — семантична метрика не критична для принципу «вірш згенеровано».
- При `OFFLINE_EMBEDDER=true` метрика стає шумом (детерміністичним хеш-вектором, який не має семантичного змісту). Для research-режиму це варто фіксувати в звітах.

**Навіщо:** окрема від `meter_accuracy` / `rhyme_accuracy` — **формальна коректність** ≠ **тематична відповідність**. Вірш може ідеально тримати ямб і ABAB, але писати про картопляні чіпси замість «весняного лісу».

### 11.4 Regeneration Success (delta accuracy)

```python
# src/infrastructure/metrics/regeneration_success.py
initial = iterations[0]        # ітерація 0 (результат initial generation)
final   = iterations[-1]       # остання ітерація (після всіх feedback-проходів)
regeneration_success = ((final.meter_accuracy - initial.meter_accuracy)
                      + (final.rhyme_accuracy - initial.rhyme_accuracy)) / 2.0
```

**Діапазон:** `[-1, 1]`. Від'ємні значення повертаються **як є** (не clamp-аться) — це свідома деградація, яку треба **бачити** у звітах як сигнал про проблеми промпту / моделі.

- `+0.3` = feedback loop підвищив середню accuracy на 30%
- `0.0` = нічого не змінилось (либо відразу було ідеально, либо feedback не допоміг)
- `-0.2` = **модель зіпсувала вірш** намагаючись виправити — тривожний сигнал

**Коли `0.0`:** якщо `len(iterations) < 2` (feedback loop не запустився; або `max_iterations=0`, або вірш був валідний з першого разу).

**Навіщо:** відділяє **ефективність корекції** від вихідної якості. Система з baseline 50% + feedback 80% — краща за систему з baseline 75% без feedback.

### 11.5 Meter / Rhyme Improvement (окремі дельти)

```python
# src/infrastructure/metrics/iteration_metrics.py
meter_improvement = final.meter_accuracy - initial.meter_accuracy
rhyme_improvement = final.rhyme_accuracy - initial.rhyme_accuracy
```

Розкладання `regeneration_success` на два канали. Дозволяє побачити **куди саме** feedback loop вклав корекцію: якщо `meter_improvement=+0.4` а `rhyme_improvement=-0.05`, то модель виправила метр і **розбила** риму — сигнал тюнити prompt-format, щоб обидва аспекти утримувались разом.

### 11.6 Feedback Iterations

```python
feedback_iterations = max(0, len(iterations) - 1)
```

Кількість викликів feedback loop-у (крім initial generation). `0` = вірш був валідний з першої спроби, `1..max_iterations` = скільки разів довелось переробляти.

**У абляційних конфігураціях:** медіанне значення цієї метрики по матриці сценаріїв — непрямий показник складності сценарію або кволості моделі.

### 11.7 Num Lines

```python
num_lines = Poem.from_text(poem_text).line_count
```

Кількість непорожніх рядків у **фінальному** вірші (після sanitization). `Poem.from_text` пропускає рядки через `_is_poem_line()` — філтрує scansion-стаби, порожні, bulleted.

**Діагностичне значення:** очікуване = `request.structure.total_lines`. Розходження сигналізує:
- sanitizer викинув реальні рядки як «сміття» (false positive) → редагувати regex-правила;
- модель видала менше/більше рядків ніж просили → тюнити промпт або піднімати `max_iterations`.

Не агрегується у середні — використовується як per-run диагностика.

---

## 12. Evaluation Harness і абляційні конфігурації

**Файли:** `src/services/evaluation_service.py` (`EvaluationService`), `src/runners/evaluation_runner.py` (`EvaluationRunner`), `scripts/run_evaluation.py`
**Сценарії:** `src/infrastructure/evaluation/scenario_data.py`, `src/infrastructure/evaluation/scenario_registry.py`
**Агрегація:** `src/infrastructure/evaluation/aggregator.py` → `DefaultEvaluationAggregator`

### Абляційні конфігурації

| Config | Semantic RAG | Metric Examples | Validation | Feedback | Призначення |
|--------|-------------|-----------------|------------|----------|-------------|
| **A** | ❌ | ❌ | ✅ | ❌ | Baseline: LLM + валідатор, без RAG, без feedback |
| **B** | ❌ | ❌ | ✅ | ✅ | LLM + Val + Feedback (без RAG) |
| **C** | ✅ | ❌ | ✅ | ✅ | Semantic RAG + Val + Feedback |
| **D** | ❌ | ✅ | ✅ | ✅ | Metric Examples + Val + Feedback |
| **E** | ✅ | ✅ | ✅ | ✅ | **Повна система** (semantic + metric examples + val + feedback) |

**Навіщо абляції:** порівнюючи конфігурації попарно, можна кількісно виміряти внесок кожного компонента:

| Порівняння | Що вимірює |
|------------|-----------|
| `A → B` | вплив feedback loop |
| `B → C` | вплив семантичного RAG (тематичне натхнення) |
| `B → D` | вплив метричних прикладів (ритмічний еталон) |
| `C → E` або `D → E` | вплив поєднання обох типів ретрівалу |

### Матриця оцінки

```python
run_evaluation_matrix(
    scenarios=[...],    # N сценаріїв
    configs=[...],      # M конфігурацій
)
# → N × M трасів + таблиця підсумків
```

### Швидкий запуск (demo)

```bash
# Запустити N01 через повну систему (E), verbose, зберегти результат
make demo

# Інший сценарій через demo
make demo SCENARIO=N03
```

Результат зберігається в `results/demo_N01_YYYYMMDD_HHMMSS.json` і `results/demo_N01_YYYYMMDD_HHMMSS.md`.

### Запуск evaluation

```bash
# Один сценарій, повна система, детальний вивід
make evaluate SCENARIO=N01 CONFIG=E VERBOSE=1

# Всі normal сценарії, конфіг C (без RAG)
make evaluate CATEGORY=normal CONFIG=C

# Всі сценарії × всі конфіги (90 запусків)
make evaluate

# З кастомним корпусом і конкретним файлом результатів
CORPUS_PATH=my_corpus.json make evaluate OUTPUT=results/run1.json

# Перевизначити структуру вірша для всіх сценаріїв
make evaluate STANZAS=3 LINES_PER_STANZA=6
```

За замовчуванням результати зберігаються в `results/eval_YYYYMMDD_HHMMSS.json`.

Параметри `STANZAS` і `LINES_PER_STANZA` (Makefile) або `--stanzas`/`--lines-per-stanza` (CLI) застосовуються до всіх обраних сценаріїв через `dataclasses.replace()` — оригінальні об'єкти не змінюються.

### Makefile-змінні для evaluation

| Змінна | За замовчуванням | Опис |
|--------|-----------------|------|
| `SCENARIO` | *(всі)* | ID сценарію: `N01`–`N05`, `E01`–`E05`, `C01`–`C08` |
| `CONFIG` | *(всі)* | Абляційна конфіг: `A`, `B`, `C`, `D`, або `E` |
| `CATEGORY` | *(всі)* | Фільтр: `normal`, `edge`, або `corner` |
| `VERBOSE` | *(вимк.)* | `1` для повних stage-by-stage трасів |
| `OUTPUT` | `results/eval_TIMESTAMP.json` | Шлях для збереження JSON (`.md`-звіт записується автоматично поруч) |
| `STANZAS` | `2` | Перевизначити кількість строф |
| `LINES_PER_STANZA` | `4` | Перевизначити рядків на строфу |

---

## 13. Сценарії тестування

**Файл:** `src/domain/scenarios.py`

18 керованих сценаріїв у трьох категоріях. Кожен сценарій визначає параметри структури вірша:

```python
@dataclass(frozen=True)
class EvaluationScenario:
    ...
    stanza_count: int = 1       # кількість строф
    lines_per_stanza: int = 4   # рядків на строфу

    @property
    def total_lines(self) -> int:
        return self.stanza_count * self.lines_per_stanza
```

Ці значення автоматично передаються в `RagPromptBuilder.build()` і визначають розмір вірша, який LLM має згенерувати. Можна перевизначити через `--stanzas`/`--lines-per-stanza` або `STANZAS`/`LINES_PER_STANZA` у Makefile.

### NORMAL (N01–N05) — типові запити

| ID | Тема | Метр | Рима | Строфи × Рядки | Навіщо |
|----|------|------|------|----------------|--------|
| N01 | Весна в лісі | ямб 4 ст. | ABAB | 1×4 (4 рядки) | Найпоширеніша форма |
| N02 | Кохання | хорей 4 ст. | AABB | 1×4 (4 рядки) | Народна пісенна традиція |
| N03 | Батьківщина | ямб 5 ст. | ABBA | 1×4 (4 рядки) | Шевченківський стиль |
| N04 | Самотність | амфібрахій 3 ст. | ABAB | 2×4 (8 рядків) | Менш поширений метр |
| N05 | Місто вночі | дактиль 3 ст. | AABB | 2×4 (8 рядків) | Урбаністична тематика |

### EDGE (E01–E05) — граничні але валідні

| ID | Особливість | Що тестує |
|----|-------------|-----------|
| E01 | ямб 2 стопи | мінімальна довжина рядка |
| E02 | ямб 6 стоп (александрин) | максимальна довжина |
| E03 | анапест | тернарний метр |
| E04 | монорима AAAA | найсуворіша рима |
| E05 | абстрактна тема | retrieval без близьких векторів |

### CORNER (C01–C08) — adversarial вхідні дані

| ID | Вхід | Що тестує |
|----|------|-----------|
| C01 | мінімальна тема `"тиша"` | graceful handling мінімального вводу |
| C02 | тема >200 символів | довгий промпт |
| C03 | тема англійською | cross-language retrieval |
| C04 | метр `"гекзаметр"` (невідомий) | помилка валідатора |
| C05 | `foot_count=1` | екстремальний мінімум |
| C06 | emoji + HTML у темі | sanitization |
| C07 | мікс укр+рос | мовна консистентність виходу |
| C08 | `foot_count=0` | нуль (degenerate input) |

---

## 14. Трасування пайплайну (PipelineTrace)

**Файли:** `src/infrastructure/tracing/pipeline_tracer.py` (`PipelineTracer`), `src/infrastructure/tracing/null_tracer.py` (`NullTracer`), `src/infrastructure/tracing/stage_timer.py` (`StageTimer`)
**Доменна модель:** `src/domain/evaluation.py` (`PipelineTrace`, `EvaluationSummary`)
**Порт:** `src/domain/ports/tracing.py` → `ITracer`, `ITracerFactory`

Кожен запуск в evaluation harness записує повний `PipelineTrace`:

```python
PipelineTrace
├── scenario_id: str              # "N01"
├── config_label: str             # "D"
├── stages: list[StageRecord]     # один запис на кожен етап
│   ├── name                      # "retrieval", "prompt_construction", ...
│   ├── input_summary             # коротко: "theme='весна', corpus_size=153"
│   ├── input_data                # ПОВНІ ДАНІ: тема, параметри або текст вірша
│   ├── output_summary            # коротко: "retrieved 5 poems, top_sim=0.8234"
│   ├── output_data               # ПОВНІ ДАНІ: тексти знайдених віршів, промпт, тощо
│   ├── metrics                   # {"num_retrieved": 5, "top_similarity": 0.8234}
│   ├── duration_sec              # час виконання етапу
│   └── error                     # None або опис помилки
├── iterations: list[IterationRecord]  # кожна ітерація feedback loop
│   ├── iteration: int            # 0 = початкова, 1 = після першого feedback
│   ├── poem_text                 # повний текст вірша на цій ітерації
│   ├── meter_accuracy            # [0,1]
│   ├── rhyme_accuracy            # [0,1]
│   └── feedback                  # список повідомлень що були відправлені до LLM
├── final_poem: str               # підсумковий вірш
├── final_metrics: dict           # meter_accuracy, rhyme_accuracy, feedback_iterations, num_lines, ...
├── total_duration_sec: float
└── error: str | None
```

Трас серіалізується в JSON через `trace.to_dict()` і зберігається якщо передати `--output results/eval.json`. Поруч автоматично генерується `.md`-звіт з таблицею порівняння конфігів та фінальними віршами для кожного сетапу (`format_markdown_report()` у `runner.py`).

---

## 15. Змінні середовища і налаштування

### Runtime (env vars)

| Змінна | За замовчуванням | Опис |
|--------|-----------------|------|
| `GEMINI_API_KEY` | — | API-ключ Gemini (обов'язково для реальної генерації) |
| `GEMINI_MODEL` | `gemini-3.1-pro-preview` | Назва моделі. Дефолт — платна (~\$2/1M in, ~\$12/1M out), найкраща якість. Альтернативи: `gemini-2.5-pro`, `gemini-2.5-flash` (free tier, гірша якість для поезії) |
| `GEMINI_TEMPERATURE` | `0.9` | `[0, 2]`. Для reasoning-моделей знизити до `0.3` зменшує CoT-ліплення у вивід |
| `GEMINI_MAX_TOKENS` | `8192` | Ліміт токенів виводу. Для reasoning ≥8192 обовʼязково (інакше `<POEM>` envelope не встигає вивестися) |
| `GEMINI_DISABLE_THINKING` | `false` | `true` → передати `ThinkingConfig(thinking_budget=0)`. Підтримується тільки Gemini 2.5; Pro-preview повертає 400 |
| `LLM_TIMEOUT_SEC` | `120` | Жорсткий timeout одного виклику. 120s для Pro, знизити до 20s для flash |
| `LLM_RETRY_MAX_ATTEMPTS` | `2` | Скільки спроб на `LLMError`. Retry на timeout марний, але страхує від 5xx / rate-limit |
| `LLM_PROVIDER` | `""` (auto) | Force provider: `gemini`, `mock`, або порожній для auto-detect |
| `CORPUS_PATH` | `corpus/uk_theme_reference_corpus.json` | Шлях до JSON-файлу тематичного корпусу |
| `METRIC_EXAMPLES_PATH` | `corpus/uk_metric-rhyme_reference_corpus.json` | Шлях до метричного корпусу |
| `LABSE_MODEL` | `sentence-transformers/LaBSE` | HuggingFace модель для ембедінгів |
| `OFFLINE_EMBEDDER` | `false` | Використовувати детерміністичний offline ембедер (для тестів) |
| `HOST` | `127.0.0.1` | Адреса сервера |
| `PORT` | `8000` | Порт сервера |
| `DEBUG` | `false` | Режим налагодження |

**Увага:** у `.env` **не пишіть inline-коментарі** — docker-compose `env_file`-парсер читає їх як частину значення. Всі пояснення на окремому рядку перед змінною. `AppConfig.from_env` має захисну санітизацію (`_str()` helper), але краще не провокувати.

Детальна довідка по всіх knob-ах, тюнинг під reasoning-моделі і таблиця типових збоїв: [docs/ua/reliability_and_config.md](./reliability_and_config.md) ([EN](../en/reliability_and_config.md)).

### Corpus management (Makefile)

| Змінна | За замовчуванням | Опис |
|--------|-----------------|------|
| `DATA_DIR` | `data` | Директорія з `.txt`-файлами віршів |
| `THEME_OUT` | `corpus/uk_theme_reference_corpus.json` | Вихідний JSON тематичного корпусу |
| `MIN_COUNT` | `1` | Мінімальна кількість віршів |
| `THEME_CORPUS` | `corpus/uk_theme_reference_corpus.json` | Шлях для `embed-theme-corpus` |
| `METRIC_OUT` | `corpus/uk_auto_metric_corpus.json` | Вихідний JSON метрично-римного корпусу |
| `SAMPLE_LINES` | *(всі)* | Кількість перших рядків вірша для аналізу |

Без `GEMINI_API_KEY` система автоматично використовує `MockLLMProvider` — достатньо для запуску тестів і перевірки структури пайплайну.

---

## 16. Діаграма потоку даних

```
ТЕМАТИЧНИЙ КОРПУС (corpus/uk_theme_reference_corpus.json)     МЕТРИЧНО-РИМНИЙ КОРПУС (corpus/uk_metric-rhyme_reference_corpus.json)
  вірші + LaBSE embeddings [768-dim]                       вірші-зразки з розміткою метру/рими
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
                     │ build_rag_  │  тема + метр + схема + структура
                     │   prompt()  │  = два блоки: тематичні + метричні приклади
                     └─────────────┘
                           │ prompt string (~600-2500 chars)
                           ▼
    ┌────────────── LLM DECORATOR STACK (зовнішній → внутрішній) ──────────────┐
    │                                                                          │
    │   LoggingLLMProvider (INFO/ERROR + duration_sec)                         │
    │     │                                                                    │
    │     ▼                                                                    │
    │   RetryingLLMProvider (exp. backoff на LLMError, до retry_max_attempts)  │
    │     │                                                                    │
    │     ▼                                                                    │
    │   TimeoutLLMProvider (жорсткий дедлайн timeout_sec)                      │
    │     │                                                                    │
    │     ▼                                                                    │
    │   SanitizingLLMProvider (allowlist-фільтр; порожнє → LLMError → retry)   │
    │     │                                ◄── record_sanitized()              │
    │     ▼                                                                    │
    │   ExtractingLLMProvider (видобуток <POEM>…</POEM>)                       │
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
                     │ Regeneration│  той самий 5-шаровий decorator-стек
                     │ llm-call    │  generate → raw → extract → sanitize → LLMError→retry
                     └─────────────┘
                           │
                     ┌─────────────┐
                     │ LineIndex-  │ ── 3 стратегії:
                     │   Merger    │    A) повний вірш (regen == original lines)
                     │             │    B) частковий splice за violation_indices
                     │             │    C) safety fallback (regen = копія original → no-op)
                     └─────────────┘
                           │
                           └── validate() → (повтор, max_iterations разів)
                                       │
                                       ▼
                                RETURN GenerationResult(poem, ValidationResult)
```

---

*Актуальний станом на квітень 2026. Ключові файли: `src/composition_root.py`, `src/config.py`, `src/services/poetry_service.py`, `src/services/evaluation_service.py`, `src/services/detection_service.py`, `src/infrastructure/pipeline/`, `src/infrastructure/stages/`, `src/infrastructure/validators/`, `src/infrastructure/llm/`, `src/infrastructure/retrieval/`, `src/infrastructure/regeneration/`, `src/infrastructure/prompts/`, `src/infrastructure/metrics/`, `src/infrastructure/tracing/`, `corpus/uk_theme_reference_corpus.json`, `corpus/uk_metric-rhyme_reference_corpus.json`.*
