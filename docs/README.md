# Документація / Documentation

Технічна довідка про архітектуру, алгоритми та особливості проєкту.
Technical reference for the project's architecture, algorithms, and design nuances.

Кожен документ доступний у двох мовах: українською у [`ua/`](./ua/) та англійською у [`en/`](./en/).
Every document is available in two languages: Ukrainian in [`ua/`](./ua/) and English in [`en/`](./en/).

---

## 🇺🇦 Українською — [`docs/ua/`](./ua/)

### Для читача, рецензента, викладача
- [**system_overview_for_readers.md**](./ua/system_overview_for_readers.md) — оглядовий документ для людини, яка хоче швидко зрозуміти, що це за проєкт. Без глибоких технічних деталей.
- [**system_overview.md**](./ua/system_overview.md) — **повний технічний огляд системи** (16 розділів): усі шари, pipeline, валідатори, метрики, evaluation harness.

### Алгоритми ключового функціоналу
- [**stress_and_syllables.md**](./ua/stress_and_syllables.md) — як визначається наголос і рахуються склади. Фундамент для валідації метру.
- [**meter_validation.md**](./ua/meter_validation.md) — перевірка метру через `PatternMeterValidator` (позиційне порівняння очікуваного і фактичного патерну наголосів з толерантністю).
- [**rhyme_validation.md**](./ua/rhyme_validation.md) — фонетична валідація рими: клаузула → IPA → Левенштейн → класифікація (EXACT/ASSONANCE/CONSONANCE/INEXACT/NONE).
- [**detection_algorithm.md**](./ua/detection_algorithm.md) — brute-force авто-детекція метру і рими для вставленого вірша.

### RAG і промпти
- [**corpora.md**](./ua/corpora.md) — два статичні корпуси: тематичний (153 вірші 6 авторів + LaBSE-ембединги) і метрико-римовий (193 верифіковані приклади, 81 комбінація метр×стопи×схема). Як побудовані, що містять, навіщо існують.
- [**semantic_retrieval.md**](./ua/semantic_retrieval.md) — LaBSE-ембеддинги + косинусна схожість + offline fallback.
- [**prompt_construction.md**](./ua/prompt_construction.md) — два промпт-будівники (RAG + регенерація), envelope-правила, інжекція прикладів.

### Цикл корекції та робота з LLM
- [**feedback_loop.md**](./ua/feedback_loop.md) — ітеративна корекція: regenerate → merge → re-validate. Стратегії LineIndexMerger.
- [**sanitization_pipeline.md**](./ua/sanitization_pipeline.md) — sentinel-extraction `<POEM>...</POEM>` + allowlist-санітизація.
- [**llm_decorator_stack.md**](./ua/llm_decorator_stack.md) — 5-шаровий decorator-стек (Logging → Retry → Timeout → Sanitizing → Extracting → Gemini).

### Дослідження та експлуатація
- [**evaluation_harness.md**](./ua/evaluation_harness.md) — 18 сценаріїв × 5 абляційних конфігів = 90 запусків. Метрики, агрегація, інтерпретація.
- [**ablation_batch_and_report.md**](./ua/ablation_batch_and_report.md) — повний batch-конвеєр: `make ablation` → `runs.csv` → paired-Δ + bootstrap CI → дашборд (HTML + JSON).
- [**reliability_and_config.md**](./ua/reliability_and_config.md) — env-змінні, timeout / retry, reasoning-моделі, типові збої.

---

## 🇬🇧 In English — [`docs/en/`](./en/)

### For readers, reviewers, instructors
- [**system_overview_for_readers.md**](./en/system_overview_for_readers.md) — top-level overview for someone who wants to quickly grasp what the project is. No deep technical detail.
- [**system_overview.md**](./en/system_overview.md) — **full technical system walkthrough** (16 sections): all layers, pipeline, validators, metrics, evaluation harness.

### Core-functionality algorithms
- [**stress_and_syllables.md**](./en/stress_and_syllables.md) — how stress is resolved and syllables are counted. Foundation for metre validation.
- [**meter_validation.md**](./en/meter_validation.md) — metre check via `PatternMeterValidator` (positional comparison of expected vs actual stress pattern with tolerance).
- [**rhyme_validation.md**](./en/rhyme_validation.md) — phonetic rhyme validation: clausula → IPA → Levenshtein → classification (EXACT/ASSONANCE/CONSONANCE/INEXACT/NONE).
- [**detection_algorithm.md**](./en/detection_algorithm.md) — brute-force metre and rhyme auto-detection for a pasted poem.

### RAG and prompts
- [**corpora.md**](./en/corpora.md) — two static corpora: theme (153 poems by 6 authors + LaBSE embeddings) and metric-rhyme (193 verified examples, 81 metre×feet×scheme combos). What they contain, how they are built, why they exist.
- [**semantic_retrieval.md**](./en/semantic_retrieval.md) — LaBSE embeddings + cosine similarity + offline fallback.
- [**prompt_construction.md**](./en/prompt_construction.md) — two prompt builders (RAG + regeneration), envelope rules, example injection.

### Correction loop and LLM integration
- [**feedback_loop.md**](./en/feedback_loop.md) — iterative correction: regenerate → merge → re-validate. LineIndexMerger strategies.
- [**sanitization_pipeline.md**](./en/sanitization_pipeline.md) — sentinel extraction `<POEM>...</POEM>` + allowlist sanitization.
- [**llm_decorator_stack.md**](./en/llm_decorator_stack.md) — 5-tier decorator stack (Logging → Retry → Timeout → Sanitizing → Extracting → Gemini).

### Research and operations
- [**evaluation_harness.md**](./en/evaluation_harness.md) — 18 scenarios × 8 ablation configs = 144 runs. Metrics, aggregation, interpretation.
- [**ablation_batch_and_report.md**](./en/ablation_batch_and_report.md) — full batch pipeline: `make ablation` → `runs.csv` → paired-Δ + bootstrap CI → dashboard (HTML + JSON).
- [**reliability_and_config.md**](./en/reliability_and_config.md) — env variables, timeout / retry, reasoning models, common failures.

---

## 📐 Architectural Decision Records

Мова: англійська (стандарт ADR) / Language: English (ADR convention).

- [**001-hexagonal-architecture.md**](./adr/001-hexagonal-architecture.md) — чому ports-and-adapters, DDD шари.
- [**002-llm-decorator-stack.md**](./adr/002-llm-decorator-stack.md) — чому саме такий decorator-стек.
- [**003-contract-tests.md**](./adr/003-contract-tests.md) — як тестуються реалізації портів.
- [**004-pipeline-state-mutability.md**](./adr/004-pipeline-state-mutability.md) — PipelineState mutability — why the one mutable domain object is intentional.

---

## 🗺️ Як орієнтуватися / Reading order

Для нового читача / **For a new reader**:

1. [`system_overview_for_readers.md`](./ua/system_overview_for_readers.md) — [EN](./en/system_overview_for_readers.md) — 10-хвилинне пояснення
2. [`../README.md`](../README.md) — запуск і ендпойнти / setup and endpoints
3. [`system_overview.md`](./ua/system_overview.md) — [EN](./en/system_overview.md) — повний технічний огляд (16 розділів)

Для розробника / **For a developer**:

1. [`stress_and_syllables`](./ua/stress_and_syllables.md) — [EN](./en/stress_and_syllables.md) (фундамент / foundation)
2. [`meter_validation`](./ua/meter_validation.md) — [EN](./en/meter_validation.md)
3. [`rhyme_validation`](./ua/rhyme_validation.md) — [EN](./en/rhyme_validation.md)
4. [`corpora`](./ua/corpora.md) — [EN](./en/corpora.md) (RAG sources)
5. [`semantic_retrieval`](./ua/semantic_retrieval.md) — [EN](./en/semantic_retrieval.md)
6. [`prompt_construction`](./ua/prompt_construction.md) — [EN](./en/prompt_construction.md)
7. [`feedback_loop`](./ua/feedback_loop.md) — [EN](./en/feedback_loop.md)
8. [`sanitization_pipeline`](./ua/sanitization_pipeline.md) — [EN](./en/sanitization_pipeline.md)
9. [`llm_decorator_stack`](./ua/llm_decorator_stack.md) — [EN](./en/llm_decorator_stack.md)
10. [`reliability_and_config`](./ua/reliability_and_config.md) — [EN](./en/reliability_and_config.md)
11. [`evaluation_harness`](./ua/evaluation_harness.md) — [EN](./en/evaluation_harness.md)
12. [`ablation_batch_and_report`](./ua/ablation_batch_and_report.md) — [EN](./en/ablation_batch_and_report.md)

Для дослідника / **For a researcher**:

1. [`system_overview_for_readers`](./ua/system_overview_for_readers.md) — [EN](./en/system_overview_for_readers.md) — 10 хв на розуміння мети
2. [`evaluation_harness`](./ua/evaluation_harness.md) — [EN](./en/evaluation_harness.md) — як інтерпретувати звіти
3. [`ablation_batch_and_report`](./ua/ablation_batch_and_report.md) — [EN](./en/ablation_batch_and_report.md) — paired-Δ конвеєр і дашборд
4. [`meter_validation`](./ua/meter_validation.md), [`rhyme_validation`](./ua/rhyme_validation.md) — формули метрик
5. [`../results/`](../results/) — актуальні прогін Markdown-звіти
