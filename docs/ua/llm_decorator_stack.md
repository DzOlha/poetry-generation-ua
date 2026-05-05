# LLM decorator stack

> Довідник про шари декораторів між pipeline-ом і реальною LLM-моделлю: що робить кожен, у якому порядку, як поширюються помилки.

## Навіщо декоратори

Pipeline звертається до LLM через єдиний абстрактний порт `ILLMProvider`. Кожна надійність-концерна (retry, timeout, чистка шуму, трейсування) оформлена як окремий декоратор, що **вкладає** в себе попередній. Це дає:

- Єдину точку конфігурації ([`_wrap_with_reliability`](../../src/infrastructure/composition/generation_llm_stack.py) у `LLMStackSubContainer`).
- Можливість вмикати / вимикати окремі шари без правок у pipeline.
- Природне підключення нових концернів (rate-limit, circuit-breaker) — просто ще один `ILLMProvider`.

## Порядок шарів (зовнішній → внутрішній)

```
LoggingLLMProvider              ← INFO/ERROR лог на кожен виклик
  └─ RetryingLLMProvider        ← повторні спроби на LLMError
      └─ TimeoutLLMProvider     ← жорсткий дедлайн
          └─ SanitizingLLMProvider   ← чистка сміття, порожній → LLMError
              └─ ExtractingLLMProvider ← видобуток <POEM>…</POEM>
                  └─ GeminiProvider / MockLLMProvider (реальний)
```

Зверху вниз кожен наступний шар бачить результат внутрішнього. Назовні поширюються лише оброблені помилки (`LLMError`-и) — виклики інфраструктурного API прихованні.

## Що робить кожен шар

| Шар | Чому саме на цьому місці | Що поширює як виняток | Роль |
|-----|---------------------------|-----------------------|------|
| `LoggingLLMProvider` ([file](../../src/infrastructure/llm/decorators/logging_provider.py)) | Зовнішній — бачить оригінальні аргументи виклику й фінальний результат після усіх внутрішніх retry/timeout. | `LLMError` (re-raise) | Структурований `INFO` на успіх / `ERROR` на помилку з `duration_sec` і `output_chars`. |
| `RetryingLLMProvider` ([file](../../src/infrastructure/llm/decorators/retrying_provider.py)) | Над timeout, щоб одне перевищення дедлайну = одна повторна спроба, а не вичерпання всього бюджету. | `LLMError` після фінальної невдалої спроби | Робить retry на `LLMError` згідно з ін'єктованою `IRetryPolicy` (за замовчуванням `ExponentialBackoffRetry`: `retry_max_attempts`, `retry_base_delay_sec`, `retry_multiplier`, `retry_max_delay_sec`). Використовує ін'єктований `sleep_fn` — у тестах виклики залишаються синхронними. |
| `TimeoutLLMProvider` ([file](../../src/infrastructure/llm/decorators/timeout_provider.py)) | Над санітизацією, щоб дедлайн вимірювався проти відповіді моделі, а не часу чистки. | `LLMError` | Запускає внутрішній виклик у daemon-потоці й робить `join(timeout_sec)`. На перевищення кидає `LLMError`; неочікувані (не-`LLMError`) винятки всередині потоку загортає в `LLMError`, щоб retry обробляв їх однаково. **Потік не вбивається** — у Python немає переносного механізму kill-thread, тому HTTP-запит продовжує виконуватись у фоні до природного завершення; лише клієнт отримує детерміністичну помилку. |
| `SanitizingLLMProvider` ([file](../../src/infrastructure/llm/decorators/sanitizing_provider.py)) | Всередині timeout/retry, але зовні extractor-а, щоб retry-спроби завжди бачили вже очищений текст. | `LLMError` якщо всі рядки відкинуто | Прогонює вихід через `IPoemOutputSanitizer`. Записує очищений текст у `ILLMCallRecorder`. Якщо sanitizer повернув `""` (відповідь — суцільний CoT/scansion), кидає `LLMError`, щоб retry попросив ще одну спробу — мовчазне повернення сміття довело б валідатор до помилкових скарг. |
| `ExtractingLLMProvider` ([file](../../src/infrastructure/llm/decorators/extracting_provider.py)) | Найвнутрішніший wrapper — поряд з реальним провайдером, щоб sentinel-обгортку CoT відрізало першою. | Pass-through (своїх винятків не кидає) | Видобуває текст між `<POEM>…</POEM>` через `IPoemExtractor`. Записує `raw` і `extracted` у `ILLMCallRecorder` для трасування. Відсутні/порожні теги — повертає вхід без змін (sanitizer підбере). |
| `GeminiProvider` / `MockLLMProvider` ([gemini.py](../../src/infrastructure/llm/gemini.py), [mock.py](../../src/infrastructure/llm/mock.py)) | Реальний провайдер у центрі. | `LLMError` від збоїв Gemini | Реальний HTTP-виклик до Gemini (також пише `usage_metadata` у recorder) або детерміністична тестова заглушка. |

## Взаємодія: що звідки бачиться

- `LoggingLLMProvider` **не бачить** внутрішніх retry-спроб — він бачить лише фінальний успіх / помилку.
- `RetryingLLMProvider` повторює спробу тільки якщо внутрішній рівень кинув `LLMError` — **і** ін'єктована політика дозволяє повтор. Дефолтна `ExponentialBackoffRetry.should_retry` свідомо короткозамикає на `LLMQuotaExceededError`: коли вичерпана денна квота, повтор у тому самому вікні лише додасть затримку перед тією ж помилкою (HTTP 429). Решта `LLMError` ретраїться, у т.ч. timeout — для timeout це часто марно (модель знову візьме стільки ж), але та ж гілка покриває transient-збої моделі (5xx, rate-limit), де повтор має сенс.
- `SanitizingLLMProvider` може кинути `LLMError` на порожньому виводі — це єдиний випадок, коли retry отримує шанс виправити «модель видала лише CoT».
- `ExtractingLLMProvider` **завжди** пише у `ILLMCallRecorder` — навіть на помилці нижнього шару. Це дає повний трейс для UI / debug.

## Поведінкові гарантії / Contract-тести

Стек покритий тестами у [`tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py`](../../tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py). Кожен декоратор окремо — і повний production-стек, складений зверху вниз — проганяється через `ILLMProviderContract`, який перевіряє і `generate`, і `regenerate_lines`. Той самий suite містить `TestFullStackPropagatesLLMError`: коли найвнутрішніший провайдер кидає `LLMError`, кожен зовнішній декоратор зобов'язаний поширити його як `LLMError`. Це фіксує підставність (substitutability), на яку спирається архітектура:

- Дисципліну обгортання неможливо тихо порушити — якщо рефакторинг змінить тип винятка чи форму повернутого значення, contract-suite впаде до code-review.
- Тести використовують `NullLLMCallRecorder` і `_NeverRetryPolicy`; реальний час чи I/O ніколи не задіяні.

## Тонкощі + відомі гачки

- **Timeout не припиняє потік.** `Thread.join(timeout)` лише звільняє клієнта. Фактичний HTTP-запит до Gemini продовжується у daemon-потоці до природного закінчення. Токени витрачаються. Єдиний спосіб зберегти їх — `asyncio`-рефакторинг pipeline-у.
- **Mock bypass.** Якщо у `Container.injected_llm` прокинуто провайдер — стек обходиться, і провайдер потрапляє у pipeline як є (див. явну гілку у [`LLMStackSubContainer.llm`](../../src/infrastructure/composition/generation_llm_stack.py)). Зверніть увагу: `MockLLMProvider`, побудований фабрикою через `LLM_PROVIDER=mock`, **усе ж** загортається стеком — обхід стосується тільки шляху `injected_llm` для тестів/CI. Для прод-коду інжектити мок **не можна**, тільки у тестах.
- **Gemini 3.x Pro preview** не підтримує `ThinkingConfig(thinking_budget=0)` — повертає 400. Тому `gemini_disable_thinking` за замовчуванням `False`. Див. [reliability_and_config.md](./reliability_and_config.md).
- **Порожній response**. `GeminiProvider` кидає `LLMError` якщо `response.text` пустий. Це сплітає напряму до retry (не до extractor + sanitizer).

## Розширення стеку

Додати новий шар — новий клас, який реалізує `ILLMProvider` і тримає `inner`. Вбудувати у [`LLMStackSubContainer._wrap_with_reliability`](../../src/infrastructure/composition/generation_llm_stack.py) у потрібному місці ланцюжка (composition root — єдине місце, де порядок декораторів відомий).

Коли додаєте декоратор, додайте відповідний contract-підклас у [`test_decorator_contracts.py`](../../tests/unit/infrastructure/llm/decorators/test_decorator_contracts.py) і оновіть `TestFullDecoratorStackContract`, щоб новий шар прогонявся й у складі повного стеку.

Приклади, які мають сенс:
- **RateLimitingLLMProvider** — sliding window на N викликів/хв, щоб не впиратися у квоту.
- **CircuitBreakerLLMProvider** — після N послідовних помилок відкривати коло і швидко фейлити, поки провайдер не відновиться.
- **CachingLLMProvider** — LRU-кеш по хешу промпту для детерміністичних виведень у тестах/CI.

Кожен такий шар **обовʼязково** має тримати семантику `ILLMProvider`: `generate(prompt) -> str`, `regenerate_lines(poem, feedback) -> str`. Помилки — тільки `LLMError` (інакше retry не спрацює).

## Див. також

- [ADR-002: LLM reliability via decorator stack](../adr/002-llm-decorator-stack.md) — короткий формат прийняття рішення.
- [sanitization_pipeline.md](./sanitization_pipeline.md) — що саме робить sanitizer + extractor.
- [reliability_and_config.md](./reliability_and_config.md) — як налаштовувати timeout / retry.
