# Пороги, ваги, дефолти — підсумок

> **Призначення:** одне місце, де можна побачити **усі числові пороги, що дійсно впливають на поведінку системи**, на якому етапі вони спрацьовують, і чому обрано саме таке значення. Якщо число не з'являється у цій таблиці — воно не керує жодним рішенням у production-конфігурації.

> **Англомовна версія:** [`../en/thresholds_reference.md`](../en/thresholds_reference.md).

---

## Карта порогів на пайплайні

```
GenerationRequest
    │
    │  ┌──── top_k = 5 ───────────────┐  thematic-retrieval
    ▼  ▼                              │
┌──────────────────────┐              │
│ 1. RetrievalStage    │ ◄────────── tematichnyi корпус (153 вірші, LaBSE)
└──────────────────────┘
    │
    │  ┌──── metric_examples_top_k = 2 (eval) / 3 (web) ───┐
    ▼  ▼                                                    │
┌──────────────────────┐                                    │
│ 2. MetricExamplesSt. │ ◄─────────────── метрико-римний корпус (193, verified)
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 3. PromptStage       │ — будує RAG-промпт
└──────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. GenerationStage  ──► LLM Decorator Stack                         │
│                                                                     │
│   LoggingLLMProvider                                                │
│     RetryingLLMProvider     ← retry_max_attempts = 2,               │
│                              base 1.0 s, multiplier 2.0,            │
│                              max delay 10.0 s                       │
│       TimeoutLLMProvider    ← timeout_sec = 120.0                   │
│         SanitizingLLMProvider                                       │
│           ExtractingLLMProvider                                     │
│             GeminiProvider  ← temperature = 0.9,                    │
│                              max_output_tokens = 16384 (production) │
└─────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 5. ValidationStage   │
│                      │
│  PatternMeterValid.  ← allowed_mismatches = 2 на рядок
│  PhoneticRhymeValid. ← rhyme_threshold = 0.55 (нормована Левенштейна)
└──────────────────────┘
    │
    │ ok? → return
    │ violations?
    ▼
┌──────────────────────┐
│ 6. FeedbackLoopStage │ ← max_iterations: web=1, API=3, batch eval=1
└──────────────────────┘
    │
    ▼
┌──────────────────────┐
│ 7. FinalMetricsStage │ — рахує 12 калькуляторів метрик (тільки в evaluation pipeline)
└──────────────────────┘                                      │
                                                              ▼
                                                   estimated_cost_usd використовує
                                                   gemini_input_price_per_m = 2.0,
                                                   gemini_output_price_per_m = 12.0
```

**Окремий пайплайн — детекція** (`/api/poems/detect`, `make detect`):

```
poem_text
    │
    ▼
FirstLinesStanzaSampler  ← sample_lines = 4 — *precondition*:
    │                       якщо < 4 непорожніх рядків → повертаємо (None, None)
    │                       інакше — ігноруємо результат семплування й
    │                       передаємо ПОВНИЙ poem_text детекторам нижче
    ▼
BruteForceMeterDetector(poem_text)
    ↑ перебирає (метр, стопи) у feet_min..feet_max = 1..6
    ↑ валідатор аналізує всі рядки вірша; приймає, якщо meter_accuracy ≥ 0.85
    │
    ▼
BruteForceRhymeDetector(poem_text)
    ↑ перебирає схеми ABAB/AABB/ABBA/AAAA на повному тексті
    ↑ приймає, якщо rhyme_accuracy ≥ 0.5
```

---

## 1. Retrieval (RAG)

| Поріг / параметр | Значення | Де визначено | Що контролює | Чому саме так |
|---|---|---|---|---|
| `top_k` (тематичний) | `5` | [`SemanticRetriever.retrieve`](../../src/infrastructure/retrieval/semantic_retriever.py), [`GenerationRequest.top_k`](../../src/domain/models/commands.py) | Скільки семантично близьких уривків додавати у блок «thematic inspiration» | 5 — компроміс: достатньо різноманіття стилів/лексики, щоб LLM не копіював один зразок, але промпт не роздувається до 4-5 К символів і вкладається у `max_output_tokens` Gemini Pro |
| `metric_examples_top_k` | `2` (evaluation) / `3` (`GenerationRequest`-default) | [`evaluation_runner.py`](../../src/runners/evaluation_runner.py), [`commands.py`](../../src/domain/models/commands.py) | Скільки верифікованих прикладів метру/рими додати у блок «meter reference» | 2-3 достатньо, щоб few-shot задав ритм без повторення цілих катренів. Обмежено через те, що метричні приклади дублюють інформацію, яка вже є у параметрах `(meter, feet, scheme)` |

---

## 2. LLM-генерація

| Поріг / параметр | Значення | Де визначено | Що контролює | Чому саме так |
|---|---|---|---|---|
| `gemini_temperature` | `0.9` | [`AppConfig`](../../src/config.py), env `GEMINI_TEMPERATURE` | Креативність генерації | Високе значення (≥ 0.8) уникає повторення однакових рядків між викликами. Для reasoning-моделей (Gemini 2.5+/3.x Pro) **рекомендовано опускати до 0.3** — зменшує leak chain-of-thought у вивід (ALL-CAPS-склади, `( - )`-розмітка). Production за замовчуванням лишає 0.9 для сумісності з Flash-моделями |
| `gemini_max_tokens` | `16384` (production `.env`) / `8192` (fallback `AppConfig`-default) / `4096` (`GeminiProvider.__init__` class default) | [`AppConfig`](../../src/config.py) і env `GEMINI_MAX_TOKENS`; production-`.env` ставить `16384` | Бюджет вихідних токенів | Reasoning-моделі (Pro 3.x) витрачають 4–6 К токенів на CoT *до* виведення `<POEM>...</POEM>`. При 4096 envelope не встигає — модель обривається на середині. 8192 — нижня межа, на якій reasoning ще встигає дописати; **production-`.env` має `16384`** із поміткою «16384 leaves headroom for chain-of-thought on reasoning-first Pro models» — тобто є запас на довші міркування і нестабільні моделі |
| `timeout_sec` | `120.0` | [`LLMReliabilityConfig`](../../src/config.py), env `LLM_TIMEOUT_SEC` | Жорсткий дедлайн одного виклику | CoT у Gemini Pro 2.5/3.x триває 60–120 с/виклик; 120 с покриває верх легітимного reasoning. Більше — модель «загубилась», `TimeoutLLMProvider` має обірвати, щоб feedback-iterator міг рухатись далі. Для Flash-моделей варто опустити до 20 с |
| `retry_max_attempts` | `2` | [`LLMReliabilityConfig`](../../src/config.py), env `LLM_RETRY_MAX_ATTEMPTS` | Скільки спроб на `LLMError` | 2 — баланс між «вкласти ще одну спробу на transient 5xx / rate-limit» і «не множити фінансові витрати, коли модель стабільно ламається». Retry на `LLMQuotaExceededError` короткозамикається у [`ExponentialBackoffRetry.should_retry`](../../src/infrastructure/llm/decorators/retry_policy.py), бо квота не відновиться у retry-вікні |
| `retry_base_delay_sec` | `1.0` | `LLMReliabilityConfig` | Базова затримка перед першою retry | Стандартний exp-backoff: достатньо, щоб transient-помилка проминула (rate-limit, мережева збійка), і недостатньо, щоб користувач помітив у UI |
| `retry_max_delay_sec` | `10.0` | `LLMReliabilityConfig` | Верхня межа затримки | При multiplier=2 і attempts=2 задіяна максимум одна затримка 1 с — поріг 10 с залишається як safety-net |
| `retry_multiplier` | `2.0` | `LLMReliabilityConfig` | Множник exp-backoff | Класичний 2× — стандарт у цьому домені, не екзотика |

---

## 3. Валідація

| Поріг / параметр | Значення | Де визначено | Що контролює | Чому саме так |
|---|---|---|---|---|
| `meter_allowed_mismatches` | `2` | [`ValidationConfig`](../../src/config.py) → [`PatternMeterValidator`](../../src/infrastructure/validators/meter/pattern_validator.py) | Скільки **реальних** (не толерованих як пірихій/спондей) розбіжностей наголосу дозволено в одному рядку | Класична поезія допускає **ритмічні варіації**: пірихії й спондеї на службових/односкладових словах фільтруються до підрахунку (див. [`meter_validation.md`](./meter_validation.md)). Поріг `≤ 0` відкидав би канонічні рядки Шевченка, Лесі Українки, Костенко. `2` емпірично пропускає классичний корпус і ловить справжні зриви |
| `rhyme_threshold` | `0.55` | [`ValidationConfig`](../../src/config.py) → [`PhoneticRhymeValidator`](../../src/infrastructure/validators/rhyme/phonetic_validator.py) | Мінімальна нормована Левенштейн-схожість IPA-clausula двох рядків, щоб рима вважалась валідною | Рима не завжди точна (чоловіча/жіноча, асонанс, дисонанс). 0.55 емпірично пропускає канонічні неточні рими в українському матеріалі (Шевченко: «душу / мусиш», ~0.5), але відсікає випадки з різною стресовою позицією, де справжня рима втрачена |
| `bsp_score_threshold` | `0.6` | [`ValidationConfig`](../../src/config.py) → [`BSPMeterValidator`](../../src/infrastructure/validators/meter/bsp_validator.py) | Мінімальний композитний BSP-score, щоб рядок вважався валідним за **альтернативною** стратегією | **Production не використовує BSP** — `meter_validator()` повертає `PatternMeterValidator`. BSP — opt-in експериментальна стратегія для дослідження. `0.6` — емпіричний поріг на верифікованому корпусі |
| `bsp_alternation_weight` | `0.50` | [`BSPAlgorithm.__init__`](../../src/infrastructure/validators/meter/bsp_algorithm.py) | Вага «регулярність чергування» у композитному BSP-score | Альтернація — найважливіший сигнал ритму, тому домінує (½ ваги) |
| `bsp_variation_weight` | `0.20` | те саме | Вага «припустимої варіативності» | Не штрафує живий ритм за відхилення в межах поетичної норми |
| `bsp_stability_weight` | `0.15` | те саме | Вага глобальної стабільності піраміди різниць | Глибокі рівні піраміди — слабший, але не нульовий сигнал |
| `bsp_balance_weight` | `0.15` | те саме | Вага розподілу наголосів по рядку | Балансує локальні vs глобальні характеристики |

> Пороги BSP-вагів сумарно дають 1.0; зміна однієї без перерозподілу інших спотворить нормування score в `[0, 1]`.

---

## 4. Feedback loop

| Поріг / параметр | Значення | Де визначено | Що контролює | Чому саме так |
|---|---|---|---|---|
| `max_iterations` | `1` (web UI, batch eval), `3` (`GenerationRequest`-default, API `/poems`) | [`evaluate.html`](../../src/handlers/web/templates/evaluate.html), [`schemas.py`](../../src/handlers/api/schemas.py), [`commands.py`](../../src/domain/models/commands.py) | Скільки разів feedback-loop може просити LLM переписати рядки після виявлення порушень | `1` — production-default: одна додаткова спроба коштує ще один платний LLM-виклик і додає 60–120 с до latency. Емпірично дає найбільший приріст на 1-й ітерації, далі швидко затухає. `3` — верхня межа, що дозволяє API і `evaluate.html`-форма (валідація `ge=0, le=3`); вище — економічно невигідно |

---

## 5. Детекція (окремий пайплайн)

| Поріг / параметр | Значення | Де визначено | Що контролює | Чому саме так |
|---|---|---|---|---|
| `detection.meter_min_accuracy` | `0.85` | [`DetectionConfig`](../../src/config.py) | Мінімальна частка валідних рядків, щоб класифікація `(метр, стопи)` була повернена | Жорсткий поріг — система каже «це ямб 4ст» лише коли впевнена, інакше повертає «не визначено». Краще нічого, ніж близький-але-не-той метр |
| `detection.rhyme_min_accuracy` | `0.5` | `DetectionConfig` | Мінімальна частка пар, що римуються | На 4-рядковому семплі агрегатна accuracy може бути лише 0.0 / 0.5 / 1.0. `0.5` пускає схему, якщо хоча б одна пара впевнено римується (другу могла зіпсувати slant-рима «душу / мусиш»). 0.75 силкував би обидві пари — занадто строго |
| `detection.sample_lines` | `4` | `DetectionConfig` | **Precondition-гейт у [`DetectionService.detect()`](../../src/services/detection_service.py)**: якщо у вірші < `sample_lines` непорожніх рядків — одразу повертаємо `(None, None)` без запуску детекторів. Сам семпл далі **не використовується** — детектори отримують повний `poem_text` і аналізують усі рядки | Катрен — найкоротша строфа, на якій схема рими (`ABAB`/`AABB`/`ABBA`/`AAAA`) взагалі визначена; коротший вірш не дає сенсу запускати brute-force перебір. Поле захищене assert-ом у `DetectionConfig.__post_init__` (інше значення змінило б контракт `IRhymeSchemeExtractor`) |
| `detection.feet_min` / `detection.feet_max` | `1` / `6` | `DetectionConfig` | Діапазон перебору кількості стоп | Збігається з production-діапазоном генерації/валідації — система розпізнає те, що сама ж може створити. 1-стопні (анапест «Мерехтить») — рідкісні, але законні; >6 — практично відсутні в українській |

---

## 6. Розрахунок вартості

| Поріг / параметр | Значення | Де визначено | Що контролює | Чому саме так |
|---|---|---|---|---|
| `gemini_input_price_per_m` | `2.0` USD | [`AppConfig`](../../src/config.py), env `GEMINI_INPUT_PRICE_PER_M` | Ціна 1 М input-токенів для метрики `estimated_cost_usd` | Опубліковані тарифи Gemini 3.1 Pro Preview (≤ 200 К контексту). Перевизначити при переході на Flash (там $0.075–$0.15/М) |
| `gemini_output_price_per_m` | `12.0` USD | те саме, env `GEMINI_OUTPUT_PRICE_PER_M` | Ціна 1 М output-токенів (включно з reasoning) | Reasoning-токени тарифікуються як output — це і пояснює великий спред input/output 1:6 |
| `delay_between_calls_sec` | `3.0` | [`BatchEvaluationService`](../../src/services/batch_evaluation_service.py), [`batch_evaluation_runner.py`](../../src/runners/batch_evaluation_runner.py) | Пауза між викликами LLM у batch-режимі | Захист від rate-limit Gemini API при 144 послідовних викликах (18 сценаріїв × 8 конфігів). 3 с — емпірично сумісно з безкоштовним rate-limit Gemini 2.5 Flash і не б'є по тарифних користувачах Pro |

---

## Як змінювати ці значення

1. **Через env vars** — для `gemini_*`, `LLM_*`, `OFFLINE_EMBEDDER`, `CORPUS_PATH`, `METRIC_EXAMPLES_PATH`. Повний перелік у [`reliability_and_config.md`](./reliability_and_config.md).
2. **Через `AppConfig`-поля** — для `validation.*` і `detection.*` (наразі без env-binding-у; редагувати у коді або інжектувати окремий `AppConfig` у тестах).
3. **Per-request override** — `top_k`, `metric_examples_top_k`, `max_iterations` приходять у `GenerationRequest` від handler-а / runner-а; web/API передають значення з форми.

> **Дисципліна:** будь-який новий поріг має або потрапити сюди, або жити локально як `_PRIVATE_THRESHOLD` усередині модуля з docstring-обґрунтуванням. Магічні числа без пояснення — табу (див. CLAUDE-style ADR `docs/adr/`).
