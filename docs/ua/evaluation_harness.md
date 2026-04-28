# Evaluation harness (дослідницький шар)

> Автоматизований рушій для **кількісного вимірювання** якості системи. 18 сценаріїв × 8 абляційних конфігів = 144 запуски за один прохід матриці. Результати агрегуються у таблиці порівняння; batch-runner розширює матрицю кількома seeds на клітинку і пише плаский CSV для подальшого аналізу внеску компонентів.

## Мета

Коли замінюється один компонент (інший метричний валідатор, новий sanitizer, інший семантичний retriever), треба знати: **чи це покращення об'єктивно**? Не «здається, краще», а «середня точність метру на 18 тестових сценаріях зросла з 0.76 до 0.81».

Це стандартна дослідницька практика — **ablation study**: фіксуємо систему, вимикаємо один компонент, міряємо, як впала якість.

## Сценарії (18 штук)

Доменні типи живуть у [`src/domain/scenarios.py`](../../src/domain/scenarios.py) (`EvaluationScenario`, `ScenarioRegistry`). Конкретні екземпляри N01–N05, E01–E05, C01–C08 — це application-level test data у [`src/infrastructure/evaluation/scenario_data.py`](../../src/infrastructure/evaluation/scenario_data.py).

Кожен сценарій несе прапорець `expected_to_succeed: bool` (за замовчуванням `True`). Два corner-кейси — **C04** (непідтримуваний метр «гекзаметр») і **C08** (`foot_count=0`) — мають `expected_to_succeed=False`. Вони навмисне падають у `MeterSpec.__post_init__` з `UnsupportedConfigError`; `EvaluationService.run_scenario` ловить це і записує trace як перерваний прогін, а не валить матрицю. Batch-runner може відкинути їх заздалегідь через `--skip-degenerate` (див. нижче).

### Normal (N01–N05) — типові випадки

| ID | Тема | Метр / стопи / рима |
|----|------|---------------------|
| N01 | Весна у лісі | ямб, 4, ABAB |
| N02 | Кохання і розлука | хорей, 4, AABB |
| N03 | Рідна земля, Україна | дактиль, 4, ABBA |
| N04 | Самотність | амфібрахій, 4, ABAB (2 строфи) |
| N05 | Місто вночі | анапест, 4, AABB (2 строфи) |

«Комфортна зона»: популярні метри, помірна довжина, типові теми.

### Edge (E01–E05) — граничні випадки

| ID | Що навантажує |
|----|---------------|
| E01 | 2-стопний ямб — дуже короткі рядки |
| E02 | 6-стопний ямб (александрійський вірш) — дуже довгі рядки |
| E03 | 6-стопний анапест з ABBA — рідкісна комбінація метр+схема |
| E04 | монорима AAAA — усі чотири рядки мають римуватися (амфібрахій 5) |
| E05 | абстрактна тема «час як безкінечна спіраль» (дактиль 5) |

Edge-сценарії тестують граничні режими: дуже коротке/довге, рідкісне, абстрактне.

### Corner (C01–C08) — складні й зламані випадки

| ID | Сценарій | `expected_to_succeed` |
|----|----------|-----------------------|
| C01 | мінімальна однослівна тема «тиша» | True |
| C02 | дуже довга багатореченнєва тема (>200 символів) | True |
| C03 | тема англійською (латиниця) | True |
| C04 | непідтримуваний метр «гекзаметр» | **False** |
| C05 | 1-стопний анапест — екстремум мінімалізму | True |
| C06 | спецсимволи / HTML / емодзі у темі — XSS-захист | True |
| C07 | змішана українсько-російська тема | True |
| C08 | `foot_count=0` — вироджений ввід | **False** |

Corner-тести — це **стрес-тести**: як система поводиться, коли користувач робить дивне.

## Абляційні конфіги (A–H)

Файл: [`src/domain/evaluation.py`](../../src/domain/evaluation.py) — див. `ABLATION_CONFIGS` і константи `STAGE_*`. Поле `AblationConfig.enabled_stages` — це frozen-set із канонічними назвами стадій; `IStageSkipPolicy` запитує `AblationConfig.is_enabled(stage.name)`, щоб вирішити, чи запускати togglable-стадію.

Обовʼязкові стадії запускаються завжди: `prompt_construction`, `initial_generation`, `final_metrics`. Togglable-стадії: `retrieval`, `metric_examples`, `validation`, `feedback_loop`.

| Конфіг | Увімкнені togglable-стадії | Суть |
|--------|---------------------------|------|
| **A** | { validation } | Baseline: LLM пише вірш сам, ми лише перевіряємо, нічого не виправляємо. Без RAG, без метричних прикладів, без feedback. |
| **B** | { validation, feedback_loop } | A + цикл виправлень. Без RAG, без метричних прикладів. |
| **C** | { retrieval, validation, feedback_loop } | B + тематичний retrieval. Без метричних прикладів. |
| **D** | { metric_examples, validation, feedback_loop } | B + метричні приклади. Без тематичного RAG. |
| **E** | { retrieval, metric_examples, validation, feedback_loop } | Повна система. |
| **F** | { retrieval, validation } | C мінус feedback. Чистий ефект RAG на перший драфт. |
| **G** | { metric_examples, validation } | D мінус feedback. Чистий ефект метричних прикладів. |
| **H** | { retrieval, metric_examples, validation } | E мінус feedback. Чистий ефект обох збагачень разом. |

**Чому саме такі конфіги:** щоб **ізолювати внесок** кожного опціонального компонента — і з feedback-циклом, і без нього (бо feedback маскує raw-ефект збагачень: репарує погані початкові варіанти й конвергує всі арки до близької якості).

З feedback (порівняння кінцевої якості):
- **A → B**: наскільки допомагає feedback loop?
- **B → C**: наскільки додає semantic RAG поверх feedback?
- **B → D**: наскільки додають метричні приклади поверх feedback?
- **D → E**, **C → E**: ортогональність двох RAG-механізмів.

Без feedback (raw-ефект на перший драфт):
- **A → F**: чистий ефект semantic RAG, не приглушений feedback-репарацією.
- **A → G**: чистий ефект метричних прикладів — головна метрика для гіпотези «metric examples скорочують ітерації».
- **A → H**: чистий ефект обох разом.
- **H → E**: маргінальний внесок feedback за умови вже-багатого промпту.

`DEFAULT_GENERATION_CONFIG` (label `"generate"`, всі togglable-стадії увімкнені) — це конфіг, з яким працює інтерактивний `/generate`.

## Pipeline матриця

[`EvaluationService.run_matrix`](../../src/services/evaluation_service.py) ітерує `scenarios × configs`, викликає `run_scenario` для кожної клітинки і конвертує отриманий `PipelineTrace` у `EvaluationSummary`. Загалом: 18 × 8 = **144 запуски** на прохід; `max_iterations=1` за замовчуванням.

Кожен прогін повертає один незмінний `PipelineTrace` (stages, iterations, фінальний вірш, фінальні метрики, повна тривалість, помилка) і один `EvaluationSummary`-рядок.

### Інʼєкція годинника

`EvaluationService.run_scenario` приймає `IClock` і таймить pipeline через `self._clock.now()` (старт) та `self._clock.now() - t_global` (тривалість). Дефолтний адаптер — `SystemClock`, який обгортає `time.perf_counter`; тести підкладають `FakeClock`, щоб перевіряти тривалість без реального годинника. Порт і `IDelayer` (див. batch-runner нижче) живуть у [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py).

## Фінальні метрики

Кожна метрика — окремий `IMetricCalculator` (`src/infrastructure/metrics/`), зареєстрований у `DefaultMetricCalculatorRegistry` через [`CalculatorRegistrySubContainer.metric_registry`](../../src/infrastructure/composition/metrics_calculator_registry.py). `FinalMetricsStage` обходить registry, викликає `calculate(EvaluationContext)` на кожному калькуляторі і пише словник у `PipelineTrace.final_metrics` (калькулятор, що кинув виняток, логиться і записується як `0.0` — метрики ніколи не валять прогін).

| Метрика | Що вимірює |
|---------|------------|
| `meter_accuracy` | `valid_lines / total_lines` від meter-валідатора. Діапазон `[0, 1]`. |
| `rhyme_accuracy` | `valid_pairs / total_pairs` від rhyme-валідатора. Діапазон `[0, 1]`. |
| `regeneration_success` | Покриття порушень між ітерацією 0 і фінальною. `1 − final_violations / initial_violations`, де violations = `(1 − meter) + (1 − rhyme)`. 1.0 = усі порушення виправлено; 0.0 = жодного; відʼємне = регенерація погіршила. Якщо ітерація 0 уже без порушень, метрика 1.0 (вакуумно успішно). |
| `semantic_relevance` | `cosine(embed(theme), embed(poem_text))`. Діагностична — з offline-ембеддером стає шумом. |
| `line_count` | `Poem.from_text(poem).line_count`. Діагностична — має збігатися з `request.structure.total_lines`. |
| `meter_improvement` | `final − initial` точність метру через ітерації. |
| `rhyme_improvement` | `final − initial` точність рими через ітерації. |
| `feedback_iterations` | Кількість виконаних feedback-ітерацій (`len(iterations) − 1`, бо ітерація 0 — це початкова валідація). |
| `input_tokens` / `output_tokens` / `total_tokens` | Сумарне використання токенів за всіма LLM-викликами прогону. |
| `estimated_cost_usd` | Токени × тарифи з `AppConfig.gemini_input_price_per_m` / `gemini_output_price_per_m`. |

## Агрегація

[`DefaultEvaluationAggregator.aggregate(summaries, configs, scenarios)`](../../src/infrastructure/evaluation/aggregator.py) — чиста обчислювальна логіка без I/O — повертає `EvaluationAggregates(by_config, by_category)`.

### By config

Для кожного `AblationConfig` усереднюємо meter / rhyme accuracy і кількість ітерацій по його прогонах, плюс кількість помилок. Виходить `ConfigAggregate`-рядок. Різниці між рядками (E − A, C − B, D − B …) кількісно показують внесок кожного компонента.

### By category

Для кожної `ScenarioCategory` (Normal / Edge / Corner) усереднюємо meter / rhyme accuracy і рахуємо помилки по всіх прогонах цієї категорії × усі конфіги. Виходить `CategoryAggregate`-рядок. Корисно бачити «система працює на Normal, валиться на Corner»-плато.

`EvaluationRunner._log_aggregates` рендерить обидва набори у структуровані лог-рядки.

## Потік `make evaluate`

Makefile-рецепт обгортає [`scripts/run_evaluation.py`](../../scripts/run_evaluation.py) → [`EvaluationRunner`](../../src/runners/evaluation_runner.py). Змінні:

| Змінна | Призначення | Дефолт |
|--------|-------------|--------|
| `SCENARIO` | Один сценарій (наприклад `N05`) | без значення = усі |
| `CONFIG` | Один абляційний label (`A`–`H`) | без значення = усі |
| `CATEGORY` | `normal` / `edge` / `corner` | без значення = усі |
| `STANZAS` | Перевизначити кількість строф | 2 |
| `LINES_PER_STANZA` | Перевизначити кількість рядків у строфі | 4 |
| `VERBOSE` | Вивести детальні трейси | без значення |
| `OUTPUT` | Файл результатів (JSON; Markdown-двійник пишеться поряд) | `results/eval_<TS>.json` |

Приклади:

```bash
make evaluate                            # усі 18 × 8 = 144 прогони
make evaluate SCENARIO=N05               # один сценарій, усі конфіги
make evaluate CATEGORY=normal CONFIG=C   # пʼять normal-сценаріїв, конфіг C
```

Runner виводить summary-таблицю, рядки by-config / by-category агрегатів і (коли задано `OUTPUT`) JSON-trace плюс сусідній Markdown-звіт.

## Потік `make ablation` (batch CSV)

[`BatchEvaluationRunner`](../../src/runners/batch_evaluation_runner.py) розширює `EvaluationService` на seeds × configs × scenarios. Повторює кожну клітинку `SEEDS` разів і стрімить по одному рядку на прогін через `IBatchResultsWriter` (за замовчуванням `CsvBatchResultsWriter`), щоб часткові результати вже були на диску, якщо процес упаде. Вихід: `<BATCH_DIR>/runs.csv` — один `BatchRunRow` на прогін.

Конструктор сервісу приймає `IDelayer`; `_iter_rows` викликає `self._delayer.sleep(delay_between_calls_sec)` між LLM-викликами (перед першим виконаним викликом — пропускається). Дефолтний `SystemDelayer` обгортає `time.sleep`; тести підкладають `FakeDelayer`, щоб перевірити throttling без реального очікування.

| Змінна | Призначення | Дефолт |
|--------|-------------|--------|
| `SEEDS` | Кількість повторень на клітинку (scenario × config) | 3 |
| `DELAY` | Секунди між LLM-викликами (подушка від rate-limit) | 3 |
| `MAX_ITERATIONS` | Кількість feedback-ітерацій на прогін | 1 |
| `BATCH_DIR` | Каталог виходу; `runs.csv` пишеться всередині | `results/batch_<TS>` |
| `RESUME` | Прочитати наявний `runs.csv` і пропустити клітинки, які вже відпрацювали | без значення |
| `SKIP_DEGENERATE` | Відкинути сценарії з `expected_to_succeed=False` (наприклад C04, C08) | без значення |
| `SCENARIO` / `CONFIG` / `CATEGORY` | Ті самі фільтри, що й у `make evaluate` | без значення |

Приклади:

```bash
make ablation                                  # 18 × 8 × 3 = 432 прогони
make ablation SEEDS=5 DELAY=5                  # більше повторень, мʼякший rate-limit
make ablation SCENARIO=N01 CONFIG=E SEEDS=10   # перевірка дисперсії на одній клітинці
make ablation SKIP_DEGENERATE=1                # пропустити C04 / C08, які зʼїдають квоту

# resume після квоти — той самий BATCH_DIR + RESUME=1
make ablation BATCH_DIR=results/batch_20260424_180000 RESUME=1
```

Семантика resume — у `BatchEvaluationRunner._load_resume_state`: рядки без поля `error` передаються в `BatchEvaluationService.run` як `preserved_rows`, а їхні трійки `(scenario_id, config_label, seed)` потрапляють у `skip_cells`. Iterator мовчки пропускає такі клітинки; рядки, що впали з помилкою, перезапускаються.

`BatchRunRow` (у `src/domain/evaluation.py`) несе ті самі метрики, що й `EvaluationSummary`, плюс `regeneration_success`, `semantic_relevance`, `seed`, `category`, та `iteration_tokens` (компактний поrowковий розклад `it=<i>:in=<n>:out=<n>`).

## Збирання Markdown-звіту

`MarkdownReporter` тепер — тонкий façade над чотирма колабораторами у [`src/infrastructure/reporting/`](../../src/infrastructure/reporting/):

- [`TableFormatter`](../../src/infrastructure/reporting/table_formatter.py) — розкладка summary-таблиці і ширини усічення.
- [`TraceFormatter`](../../src/infrastructure/reporting/trace_formatter.py) — plain-text блок одного trace-у (стадії, історія ітерацій, проміжні вірші, фінальний вірш, токени та вартість).
- [`CostCalculator`](../../src/infrastructure/reporting/cost_calculator.py) — чистий USD-helper з тарифами на мільйон токенів.
- [`MarkdownDocumentBuilder`](../../src/infrastructure/reporting/markdown_document_builder.py) — порядок секцій верхнього рівня: Generation Model → Config Legend → Summary → Aggregate by Config → Tokens & Cost → Trace Details.

Reporter поєднує їх через [`ReportingSubContainer.reporter`](../../src/infrastructure/composition/metrics_reporting.py); тарифи беруться з `AppConfig`. `JsonResultsWriter` (дефолтний `IResultsWriter`) приймає reporter, тож разом із JSON писатиметься і сусідній `.md`.

## Розкладка composition

Контейнер метрик розщеплено на два сфокусовані під-контейнери; `MetricsSubContainer` тепер — façade, що зберігає публічний API:

- [`metrics_calculator_registry.py`](../../src/infrastructure/composition/metrics_calculator_registry.py) — registry, кожен `IMetricCalculator`, `FinalMetricsStage` і `DefaultStageRecordBuilder`.
- [`metrics_reporting.py`](../../src/infrastructure/composition/metrics_reporting.py) — `MarkdownReporter`, `JsonResultsWriter`, `CsvBatchResultsWriter`, `PipelineTracerFactory`, `DefaultHttpErrorMapper`, `DefaultEvaluationAggregator`.

Додавання метрики чіпає лише calculator-registry; правки звіту чіпають лише reporting-контейнер.

## Вихідні файли

Результати експортуються у два формати одразу, коли задано `OUTPUT`:

1. **JSON** — повний `PipelineTrace` (stages, iterations, metrics) кожного прогону, пише `JsonResultsWriter`. Для програмного аналізу.
2. **Markdown** — таблиці порівняння + детальні блоки кожного прогону, складає `MarkdownReporter`. Для читання / включення у звіт.

Шлях: `results/eval_YYYYMMDD_HHMMSS.{json,md}`. Batch-вихід: `<BATCH_DIR>/runs.csv`.

## Тестове покриття

- [`tests/unit/runners/test_batch_evaluation_runner.py`](../../tests/unit/runners/test_batch_evaluation_runner.py) — драйвить `BatchEvaluationRunner` проти hand-written фейкового `BatchEvaluationService` і stub-`IScenarioRegistry`. Покриває валідацію аргументів, фільтри scenarios / configs, resume on / off, resume з відсутнім файлом, `skip_degenerate` та форвардинг kwargs. Доповнює існуюче покриття у `test_runners.py` для generate / evaluate runners.

## Запуск

### Web UI

Сторінка `/evaluate` обирає одну клітинку (scenario, config) і запускає один візуалізований trace. Не для повної матриці — для точкової діагностики.

### API

`POST /api/evaluate` із body `{"scenario_id": "N05", "config_label": "E"}`. Синхронно — повертає JSON-trace.

Matrix і batch-прогони доступні лише через CLI.

## Ключові файли

- [`src/services/evaluation_service.py`](../../src/services/evaluation_service.py) — `EvaluationService.run_scenario`, `run_matrix`
- [`src/services/batch_evaluation_service.py`](../../src/services/batch_evaluation_service.py) — `BatchEvaluationService`
- [`src/runners/evaluation_runner.py`](../../src/runners/evaluation_runner.py) — entrypoint `make evaluate`
- [`src/runners/batch_evaluation_runner.py`](../../src/runners/batch_evaluation_runner.py) — entrypoint `make ablation`
- [`src/domain/scenarios.py`](../../src/domain/scenarios.py) — `EvaluationScenario`, `ScenarioRegistry`
- [`src/infrastructure/evaluation/scenario_data.py`](../../src/infrastructure/evaluation/scenario_data.py) — екземпляри N01–N05, E01–E05, C01–C08
- [`src/domain/evaluation.py`](../../src/domain/evaluation.py) — `AblationConfig`, `ABLATION_CONFIGS`, `PipelineTrace`, `IterationRecord`, `StageRecord`, `EvaluationSummary`, `BatchRunRow`
- [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py) — `IClock`, `IDelayer`
- [`src/infrastructure/evaluation/aggregator.py`](../../src/infrastructure/evaluation/aggregator.py) — `DefaultEvaluationAggregator`
- [`src/infrastructure/metrics/`](../../src/infrastructure/metrics/) — кожен `IMetricCalculator` + `DefaultMetricCalculatorRegistry`
- [`src/infrastructure/reporting/`](../../src/infrastructure/reporting/) — façade `MarkdownReporter` + `TableFormatter` / `TraceFormatter` / `CostCalculator` / `MarkdownDocumentBuilder`
- [`src/infrastructure/composition/metrics_calculator_registry.py`](../../src/infrastructure/composition/metrics_calculator_registry.py) — wiring калькуляторів
- [`src/infrastructure/composition/metrics_reporting.py`](../../src/infrastructure/composition/metrics_reporting.py) — wiring reporting

## Налаштування за замовчуванням

| Параметр | Значення |
|----------|----------|
| Кількість сценаріїв | 18 (5 Normal + 5 Edge + 8 Corner) |
| Кількість конфігів | 8 (A–H; E — рекомендований дефолт) |
| Дефолтні feedback-ітерації | 1 |
| Дефолтні seeds (batch) | 3 |
| Дефолтна затримка між LLM-викликами (batch) | 3 с |
| Retrieval top-k | 5 (пошук) / 2 (у промпт) |
| Метричні приклади top-k | 2 |
| Строфи × рядки на строфу (CLI) | 2 × 4 |

## Тонкощі

- **Відтворюваність.** Gemini не детермінований — навіть з `temperature=0` відповіді різнитимуться між прогонами. Для строгих експериментів — `make ablation SEEDS=5` і середнє.
- **Offline-режим.** З `OFFLINE_EMBEDDER=true` `semantic_relevance` стає шумом. Інші метрики залишаються валідними.
- **Corner-сценарії спотворюють середнє.** Якщо потрібне «одне число» для порівняння конфігів — виключіть corner із середнього. By-category агрегат розводить їх в окремий рядок саме для цього.
- **Time budget.** Повна матриця ≈ 30–60 хв з реальним провайдером; повний batch (×3 seeds) ≈ 1.5–3×. Web UI підтримує лише одиничні прогони.
- **Кількість ітерацій.** `max_iterations=1` — мінімум для порівняння. Більше дає кращу якість на E, але час прогону росте лінійно.

## Див. також

- [`system_overview.md`](./system_overview.md) — оглядовий тур системи.
- [`feedback_loop.md`](./feedback_loop.md) — що саме вимикається в конфігах A та D.
- [`semantic_retrieval.md`](./semantic_retrieval.md) — що вимикається в конфігах A, B, D.
- [`meter_validation.md`](./meter_validation.md), [`rhyme_validation.md`](./rhyme_validation.md) — формули метрик.
