# Санітизація виходу LLM

> Як система видобуває і чистить вірш із сирого виходу моделі. Дві взаємодоповнюючих стадії: **видобуток по тегах** + **allowlist-санітизація**.

## Проблема

Reasoning-моделі (Gemini 2.5+ / 3.x Pro) видають великий chain-of-thought, у який може «просочуватися»:

- Англомовні міркування: `"Let's try:"`, `"Perfect dactyl!"`, `"Wait, "мої" -> мо-Ї."`.
- Наголосова нотація: `КрОки`, `тІ(4)`, `(u - u - u -)`.
- Посклалдовий дефіс: `за-гу-бив-ся`, `о-бе-рЕж-ні`.
- Номери складів у дужках: `Слу(1) жи(2) ли(3)`.
- Голі послідовності цифр: `1 2 3 | 4 5 6 | 7 8`.
- Bullet-и / markdown: `* C2:`, `// коментар`.
- Фрагменти обрубаного виходу: `).`, `,.`, порожні рядки.

Все це потрапляє у валідатор → брехлива звітність, даремні ітерації, скажений UI.

## Двошарова стратегія

### Шар 1 — Sentinel extractor

Модель **просять** загорнути фінальний вірш між тегами:

```
<POEM>
Тихо спить у місті ніч
Ліхтарі горять в імлі
</POEM>
```

Інструкція живе у [rag_prompt_builder.py](../../src/infrastructure/prompts/rag_prompt_builder.py) та [regeneration_prompt_builder.py](../../src/infrastructure/prompts/regeneration_prompt_builder.py), плюс у system-prompt Gemini ([gemini.py](../../src/infrastructure/llm/gemini.py)).

[`SentinelPoemExtractor`](../../src/infrastructure/sanitization/sentinel_poem_extractor.py) толерантний до реальних збоїв моделі:

- **Кілька `<POEM>` блоків** → беремо **останній** (часто це фінальна редакція після CoT).
- **Тільки відкритий тег без закриваючого** → беремо весь хвіст після останнього `<POEM>` (обрубаний по `max_tokens` вивід).
- **Порожній блок `<POEM></POEM>`** → повертаємо вхід незміненим (нехай sanitizer підбирає).
- **Немає тегів** → повертаємо вхід незміненим. Не фейлимо — у моделі буває, але sanitizer має шанс врятувати вірш зі сирого CoT.

Порівняння регістронезалежне: `<poem>` / `<Poem>` також працюють.

### Шар 2 — Allowlist-санітизація

[`RegexPoemOutputSanitizer`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py) приймає текст від extractor-а і викидає **рядки**, які не відповідають правилам.

Підхід принципово **whitelist, а не blacklist**: кожен символ рядка має належати до множини дозволених. Усе інше — garbage.

**Дозволені символи:**

- Українська кирилиця: А-Я, а-я, І, Ї, Є, Ґ (і малі)
- Комбінований акут `\u0301` (наголосова позначка)
- Апостроф: `'`, `’`, `ʼ`
- Базова пунктуація: `. , ! ? : ;`
- Трикрапка `…`
- Тире: `—`, `–`, дефіс `-`
- Лапки: `"`, `„`, `"`, `"`, `«`, `»`
- Круглі дужки `( )` (для легітимних асайдів типу `Я думав (мовчки)`)
- Пробіл

**Усе інше** — латинські літери, цифри, `|`, `/`, `\`, `<>`, `[]`, `{}`, `=`, `+`, емоджі, стрілки `→` / `->` — автоматично дискваліфікує рядок.

### Додаткові behavioural-правила

Allowlist не ловить cyrillic-only сміття. Три додаткові перевірки:

1. **Мінімум 1 кирилична літера.** Рядок типу `).` або `,.` з самої пунктуації — не поезія.
2. **ALL-CAPS стрес-маркер.** Малий → великий у одному токені (`КрО`, `рЕж`, `тІ`) = scansion notation.
3. **Дефіс у ≥2 місцях між кирилицею.** `за-гу-бив-ся` — склади, не слово.
4. **Bullet-префікс.** `*`, `#`, `//`, або `- ` (з пробілом) на початку. Em-dash `— ` **дозволений** — це діалогова репліка.

### Salvage-пас перед перевіркою

Перед тим як дропати рядок, sanitizer **рятує** текст у частих випадках:

- Парен-блок зі scansion-наповненням стрипається: `Темрява хутає місто, (Те-мря-ва ху-та-є)` → `Темрява хутає місто,`.
- Продубльована пунктуація після стрипу згортається: `клас. (scansion).` → `клас..` → `клас.`.
- Легітимні дужки зберігаються: `Я думав (мовчки, тихо) про зорю` лишається незмінним (кирилиця + пунктуація в дужках — не scansion).

Парен уважається «scansion-flavoured» якщо всередині є цифра, латинська літера, стрілка (`->`, `=>`), лоуер-аппер Cyrillic, або intra-word дефіс.

### Двопоровий мінімум кириличних літер

У [`Poem.from_text`](../../src/domain/models/aggregates.py) є друге стрічкове правило:

- Рядок, що закінчується на `. , ! ? ; : …` — **завершене висловлювання** → мінімум **2** кириличні літери.
- Рядок без терминальної пунктуації — потрібно **5** (щоб відсіяти scansion-стаби на кшталт `КО`, `жен`, `шу`).

Це дозволяє легітимним **коротким метрам** (ямб 1-стопний, сценарій C05) вижити: `У сні.` має 4 літери + крапку → пропускається. А `жен` без крапки — дропається.

## Що відбувається якщо sanitizer викинув УСЕ

Повертається **порожній рядок**. [`SanitizingLLMProvider`](../../src/infrastructure/llm/decorators/sanitizing_provider.py) бачить порожнє і кидає `LLMError`. Це сигнал для retry-декоратора спробувати ще раз. Якщо ретраї вичерпано, pipeline фейлить з повідомленням *«LLM produced no valid poem lines after sanitization (response was pure reasoning/scansion)»*.

**Чому не повертаємо оригінал «на крайній випадок»** — бо це отруює валідатор: він отримує сміття, рапортує що-небудь (зазвичай 0% і три порушення), користувач бачить нерозбірливу відповідь. Ліпше чисто фейлнути.

## Ідемпотентність

Обидві стадії ідемпотентні: `extract(extract(x)) == extract(x)` і `sanitize(sanitize(x)) == sanitize(x)`. Після першого проходу текст не містить ні `<POEM>` envelope, ні символів поза allowlist-ом, тому другий прохід не знайде, що чистити. Це важливо тому, що retry-спроби генерації повторно проходять той самий decorator-стек, а regeneration-промпт згодовує моделі попередній (вже санітизований) вірш — подвійна обробка не повинна псувати валідний вивід на edge-випадках.

## Контракт envelope із промптом

Envelope `<POEM>...</POEM>` — це контракт, який ми домовляємось з моделлю у промпті. Обидва [`RagPromptBuilder`](../../src/infrastructure/prompts/rag_prompt_builder.py) і [`NumberedLinesRegenerationPromptBuilder`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) виводять явні блоки `OUTPUT ENVELOPE (mandatory)`, у яких модель просять загорнути фінальну відповідь у теги. `GeminiProvider` додатково повторює правило у `system_instruction`, бо Gemini надає system-промптам вищий пріоритет. Деталі — у [prompt_construction.md](./prompt_construction.md).

## Трейсування

Extractor + Sanitizer пишуть у [`ILLMCallRecorder`](../../src/domain/ports/llm_trace.py) на кожен виклик. Production-адаптер — [`InMemoryLLMCallRecorder`](../../src/infrastructure/tracing/llm_call_recorder.py), який тримає дані останнього виклику:

- `raw` — сирий вивід моделі (до extractor-а), записується `ExtractingLLMProvider` до видобутку
- `extracted` — текст після стрипу `<POEM>` envelope, записується `ExtractingLLMProvider` після видобутку
- `sanitized` — текст після allowlist + salvage, записується `SanitizingLLMProvider` (записується **навіть коли порожній** — щоб у трейсі було чітко видно «sanitizer викинув усе», а не залишилося гадати)
- token usage (`input_tokens` / `output_tokens`) — пише `GeminiProvider._record_usage`

`record_raw` обнуляє `extracted` / `sanitized` у `""`, щоб застаріле значення з попереднього виклику не «спливло», якщо ці стадії пропустяться у наступному. Snapshot читається у [`ValidationStage`](../../src/infrastructure/stages/validation_stage.py) (ітерація 0) та [`ValidatingFeedbackIterator`](../../src/infrastructure/regeneration/feedback_iterator.py) (ітерації 1+) і кладеться у `IterationRecord.raw_llm_response` / `.sanitized_llm_response`. UI відображає його у блоці «LLM trace (raw / sanitized)» на сторінках генерації і оцінки абляцій — щоб розробник бачив що саме видала модель і що саме отримав валідатор.

## Поширення змін

Додати нове правило дропу → додати регекс + перевірку у [`_is_garbage`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py). Додати кейс salvage → доповнити [`_paren_is_scansion`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py).

**Обовʼязково** додай unit-тест з конкретним зразком garbage-виводу у [`tests/unit/infrastructure/sanitization/`](../../tests/unit/infrastructure/sanitization/) — цей шар найбільше страждає від regression-ів (модель завжди вигадує новий формат leakage).

## Див. також

- [llm_decorator_stack.md](./llm_decorator_stack.md) — де sanitizer сидить у стеку і як його викликають.
- [feedback_loop.md](./feedback_loop.md) — як невалідний вивід потрапляє у feedback-цикл.
