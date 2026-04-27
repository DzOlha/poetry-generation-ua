# Цикл зворотного звʼязку

> Алгоритм ітеративного виправлення вірша: як pipeline перетворює feedback валідатора на regeneration-промпт, як зливає виправлені рядки з попередньою версією, коли зупиняється і як виставляє debug-дані кожної ітерації назовні.

## Огляд

Після початкової генерації + валідації система має набір структурованих порушень: `LineFeedback` для метру і `PairFeedback` для рими. Замість того щоб залишити вірш як невалідний, запускається цикл:

```
ітерація N (N ≥ 1):
  1. якщо stop_policy каже «досить» → break
  2. взяти поточний вірш (prev_poem) і feedback з попередньої ітерації
  3. попросити LLM виправити (regenerate_lines АБО повна регенерація)
  4. злити (merger) нові рядки з prev_poem
  5. повторно валідувати злитий вірш → новий feedback
  6. записати IterationRecord у trace (зі snapshot-ами LLM)
```

Ціль — **точкова корекція**: не перепроганяти весь вірш, а замінити лише ті рядки, що отримали violation. Це економить токени і часто зберігає семантику.

## Структура pipeline

Feedback loop — це остання togglable-стадія у генераційному pipeline:

```
FeedbackLoopStage  (skip, коли ablation-конфіг вимикає АБО валідацію
        │           було пропущено)
        ▼
ValidatingFeedbackIterator   (оркеструє цикл ітерацій)
        │
        ├── IFeedbackCycle           — ValidationFeedbackCycle
        │     ├── IMeterValidator
        │     ├── IRhymeValidator
        │     └── IFeedbackFormatter — UkrainianFeedbackFormatter
        │
        ├── IRegenerationMerger      — LineIndexMerger
        │
        ├── IIterationStopPolicy     — MaxIterationsOrValidStopPolicy
        │
        ├── ILLMProvider             — повний decorator stack
        │
        └── ILLMCallRecorder         — фіксує raw / extracted /
                                       sanitized response кожної ітерації
```

| Клас / файл | Роль |
|-------------|------|
| [`FeedbackLoopStage`](../../src/infrastructure/stages/feedback_stage.py) | Façade pipeline-стадії. Шанує ablation skip-policy і пише завершальний `StageRecord` із підсумком циклу. |
| [`ValidatingFeedbackIterator`](../../src/infrastructure/regeneration/feedback_iterator.py) | Головний оркестратор. Пробігає `range(1, max_iterations + 1)`, ловить `DomainError`, пише по одному `IterationRecord` на ітерацію. |
| [`ValidationFeedbackCycle`](../../src/infrastructure/regeneration/feedback_cycle.py) | Поєднує meter/rhyme валідатори + feedback-formatter в один виклик `.run()` → `FeedbackCycleOutcome`. |
| [`LineIndexMerger`](../../src/infrastructure/regeneration/line_index_merger.py) | Сплайсить регенеровані рядки назад у попередній вірш за структурованими індексами порушень. |
| [`MaxIterationsOrValidStopPolicy`](../../src/infrastructure/regeneration/iteration_stop_policy.py) | Стоп-правило: вірш валідний АБО досягнуто ліміту ітерацій. |
| [`NumberedLinesRegenerationPromptBuilder`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) | Будує regeneration-промпт з нумерованими рядками + bullet-списком порушень. |
| [`UkrainianFeedbackFormatter`](../../src/infrastructure/feedback/ukrainian_formatter.py) | Рендерить `LineFeedback` / `PairFeedback` у природномовні рядки, які бачить LLM. |

## Алгоритм ітерації у деталях

Дивись [`feedback_iterator.py`](../../src/infrastructure/regeneration/feedback_iterator.py); коментарі нижче.

### Крок 1: перевірка stop-політики

`MaxIterationsOrValidStopPolicy.should_stop(iteration, max_iterations, meter_result, rhyme_result, history)` повертає `True` якщо:
- `iteration > max_iterations`, **АБО**
- `meter_result.ok and rhyme_result.ok` (вірш уже валідний — продовжувати нема сенсу).

Додати нову політику (наприклад «стоп після N послідовних регенерацій без покращення») = реалізувати `IIterationStopPolicy` і прокинути її через composition root.

### Крок 2: вибір стратегії регенерації

Iterator перевіряє **поточну кількість рядків** у віршi. Якщо вона не дорівнює `request.structure.total_lines` (наприклад, sanitizer прибрав CoT-leak і вийшло 3 замість 4) — робиться **повна регенерація** через `llm.generate(state.prompt)` з оригінальним промптом, бо посткорекція не відновить втрачений рядок.

Інакше — **часткова регенерація** через `llm.regenerate_lines(state.poem, feedback_messages)`.

### Крок 3: прохід через decorator stack

`llm.generate` / `llm.regenerate_lines` йдуть через увесь [decorator stack](./llm_decorator_stack.md): logging → retry → timeout → sanitizing → extracting → Gemini. Після цього `llm_snapshot = self._llm_recorder.snapshot()` забирає `raw` / `extracted` / `sanitized` тексти + token usage для trace-у.

### Крок 4: очищення та перевірка

```python
regenerated = Poem.from_text(raw).as_text()
if not regenerated:
    state.poem = prev_poem        # суцільне сміття — лишаємо попередній
```

`Poem.from_text` знову фільтрує (див. [sanitization_pipeline.md](./sanitization_pipeline.md)). Якщо нічого не вціліло — вірш не оновлюється. Наступна валідація видасть ті ж порушення, лічильник ітерацій росте, stop-policy рано чи пізно зробить `break`.

### Крок 5: злиття через `LineIndexMerger`

Це найцікавіше. У [`LineIndexMerger.merge()`](../../src/infrastructure/regeneration/line_index_merger.py) три гілки:

**Case A — повна поема.** Якщо `regenerated` має рівно стільки ж рядків, скільки `original` → повертаємо `regenerated` як є. Модель виправила все сама.

**Case B — часткове сплайсення.** Якщо `regenerated` коротший:
1. Збираємо індекси порушень із `LineFeedback.line_idx` і `PairFeedback.line_b_idx` (rhyme-merger завжди переписує **B**-рядок у парі).
2. По відсортованих індексах вставляємо кожен регенерований рядок в `original` на позицію відповідного порушення.

Якщо у merger-а немає придатних індексів порушень або менше регенерованих рядків, ніж позицій до заповнення, повертається `regenerated` без змін.

**Case C — safety fallback.** Якщо кожен рядок у `regenerated` — верботім-копія наявного `original`-рядка, модель просто пропустила violating-рядки замість того щоб переписати їх. Сплайсити чисті рядки на violation-позиції означало б тихо знищити рими. Повертаємо `original` без змін.

Після спецгілки «повна регенерація» (Крок 2) злиття не відбувається — iterator просто перезаписує `state.poem = regenerated`, бо оригінал уже зіпсований і сплайсити в нього небезпечно.

### Крок 6: перевалідація + запис ітерації

Злитий вірш проходить через `ValidationFeedbackCycle.run()` → нові `m_result`, `r_result`, `feedback_messages`. У trace додається `IterationRecord`:

```python
IterationRecord(
    iteration=it,
    poem_text=state.poem,
    meter_accuracy=m_result.accuracy,
    rhyme_accuracy=r_result.accuracy,
    feedback=feedback_messages,
    duration_sec=t_iter.elapsed,
    raw_llm_response=llm_snapshot.raw,
    sanitized_llm_response=llm_snapshot.sanitized,
    input_tokens=llm_snapshot.input_tokens,
    output_tokens=llm_snapshot.output_tokens,
)
```

Поля trace (`raw_llm_response`, `sanitized_llm_response`, `input_tokens`, `output_tokens`) живлять debug-перегляд `/evaluate`-сторінки і рядок токенів-та-вартості Markdown-звіту по кожній ітерації.

## Структуровані feedback-обʼєкти

`LineFeedback` і `PairFeedback` живуть у [`src/domain/models/feedback.py`](../../src/domain/models/feedback.py) (їх перенесли сюди з попереднього `src/domain/feedback.py`).

- **`LineFeedback`** — meter-порушення для одного рядка. Поля: `line_idx`, `meter_name`, `foot_count`, `expected_stresses`, `actual_stresses`, `total_syllables`, `expected_syllables`, `extra_note`.
- **`PairFeedback`** — rhyme-порушення між двома рядками. Поля: `line_a_idx`, `line_b_idx`, `scheme_pattern`, `word_a`, `word_b`, `rhyme_part_a`, `rhyme_part_b`, `score`, `clausula_a`, `clausula_b`, `precision`.

Це dataclass-и, якими користуються і merger (читає `line_idx` / `line_b_idx`), і formatter (рендерить як природномовні рядки). Merger **не парсить** вихід formatter-а — він читає структуровані обʼєкти напряму, тому формат промптної строки можна змінювати без поломки злиття.

`format_all_feedback(formatter, line_fbs, pair_fbs)` — невеликий хелпер, що рендерить спершу meter-feedback, потім rhyme-feedback через будь-який обʼєкт, що задовольняє структурний тип `_FeedbackFormatterProto`.

### `UkrainianFeedbackFormatter`

`IFeedbackFormatter` реалізовано у [`UkrainianFeedbackFormatter`](../../src/infrastructure/feedback/ukrainian_formatter.py), який рендерить рядки для LLM:

- `format_line(LineFeedback)` → `"Line N violates <meter>… Expected stress on syllables: … Actual stress on syllables: … Rewrite only this line, keep the meaning."` (1-based нумерація рядків, опційний натяк shorten/lengthen за складами).
- `format_pair(PairFeedback)` → `"Lines A and B should rhyme (scheme XYZW). Expected rhyme with ending '…'. Current ending '…' does not match (score: 0.45). Rewrite line B keeping the meaning and meter."` (з опційним clausula- і precision-полем).

## Формат regeneration-промпту

[`NumberedLinesRegenerationPromptBuilder`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) будує щось на кшталт:

```
You are given a Ukrainian poem with line numbers and a list of violations.
Fix ONLY the lines mentioned in the feedback. Copy all other lines exactly unchanged.
Return the COMPLETE poem — every line, in the correct order — with no line numbers, no commentary, no markdown.

OUTPUT ENVELOPE (mandatory):
Wrap your FINAL corrected poem between the literal tags <POEM> and </POEM>. ...

POEM (with line numbers for reference):
1: Спинися, мить, на цім порозі,
2: Де тихо світяться вогні.
3: Замри на зоряній дорозі,
4: Навій чарівний сон мені.

VIOLATIONS TO FIX:
- Line 1 violates ямб meter ...
- Line 3 violates ямб meter ...
```

Модель має повернути **повний вірш** (усі рядки в порядку), але переписати **лише флаговані**. Merger далі обробляє відповідь: Case A, якщо кількість рядків збережено; Case B, якщо повернуто лише виправлені.

Промпт **обовʼязково** вимагає загорнути вірш в `<POEM>…</POEM>`-envelope (див. [sanitization_pipeline.md](./sanitization_pipeline.md)) і забороняє склади через дефіс, all-caps токени, scansion-нотацію, голі цифри, англомовні коментарі тощо.

## Метрика `RegenerationSuccessCalculator`

Успіх feedback-loop вимірює [`RegenerationSuccessCalculator`](../../src/infrastructure/metrics/regeneration_success.py) (зареєстрований у metric registry як `regeneration_success`). Формула:

```
violations(it) = (1 − meter_accuracy(it)) + (1 − rhyme_accuracy(it))
score = 1 − final_violations / initial_violations   (0, якщо ітерацій менше за 2)
```

Тож `1.0` = усі початкові порушення виправлено, `0.0` = жодного, відʼємне = цикл погіршив. Якщо вірш на ітерації 0 уже без порушень, метрика вакуумно `1.0`. Така форма «покриття порушень» краща за raw delta accuracy: метрика, що вже на стелі (наприклад rhyme = 100%), не може покращитися і несправедливо тягне дельта-середнє вниз.

## Захисні інваріанти

- **Обрубати при `DomainError`.** Будь-яка помилка всередині тіла циклу (`LLMError`, `ValidationError`, …) → запис `StageRecord(name=f"feedback_iter_{it}", error=...)` і `break`. Pipeline виживає, прогін не падає.
- **Не переписувати порожнім.** Якщо sanitizer повернув порожнє — лишаємо `prev_poem`.
- **Не втратити рядки.** Правила merger-а гарантують: кількість рядків у `state.poem` не може зменшитися.
- **Ітерацію 0 створює інша стадія.** [`ValidationStage`](../../src/infrastructure/stages/validation_stage.py) пише `IterationRecord(iteration=0, …)` після початкової валідації; iterator пише записи лише для `iteration >= 1`.

## Налаштування

- **`max_iterations`** у `GenerationRequest`: фактичний ліміт ітерацій. Web-форма обмежує `[0, 3]`. `0` = без feedback-loop взагалі (лише початкова генерація + валідація).
- **Ablation-перемикач:** `feedback_loop` — togglable-стадія. Конфіг `A` тримає її вимкненою; `B`, `C`, `D`, `E` — увімкненою.
- **`LLM_TIMEOUT_SEC` / `LLM_RETRY_MAX_ATTEMPTS`** — кожен `llm.regenerate_lines` йде через decorator stack. Див. [reliability_and_config.md](./reliability_and_config.md).
- **`iteration_stop_policy`** — замінити на власну реалізацію `IIterationStopPolicy` у composition root.

## Тонкощі

- **Ітерація 0 ≠ регенерація.** Ітерація 0 — це початкова генерація + перша валідація; її створює `ValidationStage`, а не iterator.
- **Повна регенерація на невідповідність довжини — окрема гілка.** Виконується *до* merger-а і перезаписує `state.poem` напряму — Cases A/B/C merger-а у цій гілці не використовуються.
- **`cached_feedback`** у `PipelineState` — `ValidationStage` форматує початковий feedback один раз і зберігає його; iterator перевикористовує це для першої ітерації, щоб не форматувати двічі.
- **Token snapshots.** Кожен `IterationRecord` несе `input_tokens` / `output_tokens` від recorder-а LLM. `0` означає «не доступне» (mock-адаптер, safety block, дрейф SDK) — споживачі мають трактувати це як «невідомо», а не як «безкоштовно».

## Типові збої

| Симптом | Причина | Що робити |
|---------|---------|-----------|
| Ітерація 0 і 1 — ідентичне сміття | Sanitizer пропустив garbage, merger Case A повернув той самий текст | Додати правило у sanitizer (див. [sanitization_pipeline.md](./sanitization_pipeline.md)) |
| 3 рядки замість 4 у фінальному вірші | `Poem.from_text` викинув рядок нижче `_MIN_CYR_LETTERS` | Перевірити правила у `src/domain/models/aggregates.py` |
| Ітерація 1 робить усе гірше | Regeneration-промпт отримав неточний feedback | Перевірити `UkrainianFeedbackFormatter` і структурний `LineFeedback` |
| Timeout на `regenerate_lines` → ретрай теж timeout | Reasoning-модель з замалим `max_tokens` | Підняти `GEMINI_MAX_TOKENS` або `LLM_TIMEOUT_SEC` |

## Див. також

- [`evaluation_harness.md`](./evaluation_harness.md) — як цикл вписаний в ablation-матрицю і які конфіги його вимикають.
- [`llm_decorator_stack.md`](./llm_decorator_stack.md) — через що проходить кожен `llm.*` виклик.
- [`sanitization_pipeline.md`](./sanitization_pipeline.md) — де чиститься raw response.
- [`reliability_and_config.md`](./reliability_and_config.md) — timeout, retry, тюнинг.
