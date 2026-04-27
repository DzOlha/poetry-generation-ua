# Побудова промптів

> Два промпт-будівника обслуговують два сценарії: початкова генерація та регенерація у feedback-циклі. Обидва виводять в одному форматі (`<POEM>...</POEM>` envelope), але вміст різний.

## Шари контексту

Перед моделлю система збирає кілька шарів інформації:

1. **Тема і параметри** — що генерувати (тема, метр, кількість стоп, схема рими, кількість строф і рядків у строфі).
2. **Тематичні приклади** — до *k* віршів із корпусу, семантично близьких до теми. Список згортається до порожнього, якщо стадію retrieval пропущено або вона нічого не знайшла — заголовок «Use the following poetic excerpts...» все одно виводиться, але без прикладів під ним. Див. [`semantic_retrieval.md`](./semantic_retrieval.md).
3. **Метрично-римові приклади** — до *k* віршів з іншого корпусу, які **точно** відповідають заданому метру+стопам+схемі. **Повністю опціональний** блок: якщо стадію метричних прикладів пропущено або у корпусі немає збігів — весь блок (заголовок + приклади) випадає з промпту. Див. §«Метричні приклади» нижче.
4. **Формат вихідного envelope** — `<POEM>…</POEM>` з усіма правилами.
5. **Заборони** — ніяких сценаріїв scansion, ALL-CAPS, англійських слів, markdown, digit-нумерації складів тощо.

На регенерації додається:

6. **Поточний вірш із нумерацією рядків** — `1: лінія перша\n2: лінія друга\n...`
7. **Bullet-список порушень** — `- Рядок 2: на 1 склад довше за очікуване` тощо.

Чи з'явиться опціональний шар у конкретному прогоні — вирішує на етапі побудови pipeline-у [`IStageSkipPolicy`](../../src/infrastructure/pipeline/skip_policy.py): ablation-дослідження та легкі сценарії можуть вимикати retrieval та/або метричні приклади, і prompt builder отримує порожні списки, через що відповідні блоки зникають.

## Зв'язок із LLM-викликом

Побудова промпту — це вхід для одного виклику `ILLMProvider.generate(prompt)` (початкова генерація) або `ILLMProvider.regenerate_lines(poem, feedback)` (ітерації feedback). Цей виклик іде через [decorator-стек](./llm_decorator_stack.md): logging → retry → timeout → sanitize → extract → реальний провайдер. Контракт `<POEM>...</POEM>` у промпті — це саме те, на що пізніше спирається `SentinelPoemExtractor`, щоб відрізати chain-of-thought від відповіді — див. [`sanitization_pipeline.md`](./sanitization_pipeline.md).

## Промпт для початкової генерації (RAG)

[`RagPromptBuilder.build(request, retrieved, examples)`](../../src/infrastructure/prompts/rag_prompt_builder.py) складає промпт із таких блоків у заданому порядку:

### Блок 1: тематичні приклади

```
Use the following poetic excerpts as thematic inspiration (do not copy):

<текст вірша 1>

<текст вірша 2>
```

Інструкція «**do not copy**» критична: без неї модель починає верботімно відтворювати Шевченка у відповіді. Форматер обʼєднує приклади через `\n\n`.

### Блок 2: метричні приклади (опціонально)

```
Use these verified examples as METER and RHYME reference (they demonstrate
ямб meter with ABAB rhyme scheme — follow this rhythm and rhyme pattern exactly):

<приклад 1 з коректним метром+римою>

<приклад 2>
```

Опціональний: якщо корпус метричних прикладів не знайшов нічого для `(meter, foot_count, rhyme)` — блок пропускається повністю. Формулювання «**follow this rhythm and rhyme pattern exactly**» замінює «do not copy» — тут нам треба, щоб модель справді взяла ритм, хоч і не слова.

### Блок 3: основна інструкція

```
Theme: <тема>
Meter: <метр>
Rhyme scheme: <схема>
Structure: <stanza_count> stanza(s) of <lines_per_stanza> lines each (<total_lines> lines total)
Generate a Ukrainian poem with exactly <total_lines> lines.
```

### Блок 4: envelope правила

```
OUTPUT ENVELOPE (mandatory):
Wrap your FINAL poem between the literal tags <POEM> and </POEM>.
You may reason freely BEFORE <POEM>. Everything between <POEM> and </POEM>
must be ONLY clean Ukrainian poem lines in normal orthography — one line
per verse line, exactly <N> lines, no blank separators other than one newline
between lines. Emit </POEM> immediately after the last poem line; write nothing
after it.
```

Навмисне дозволяємо моделі «думати вголос перед тегом» — це пʼять токенів, які дозволяють reasoning-моделі (Gemini 2.5+) розвантажити CoT-канал. Без цього вона все одно буде думати, але намагатиметься приховати, і результат буде плутаним.

### Блок 5: строгі правила формату

```
STRICT FORMAT RULES FOR THE CONTENT BETWEEN <POEM>...</POEM>:
- The first token after <POEM> MUST be a Cyrillic letter.
- Every output line MUST contain Ukrainian words; lines with only
  punctuation/digits/scansion are forbidden.
- NO ALL-CAPS words marking stress (forbidden: 'І-ДУТЬ', 'БІЙ').
- NO syllable hyphenation inside words (forbidden: 'За-гу-бив-ся').
- NO syllable numbering in parentheses (forbidden: 'Слу(1) жи(2)').
- NO scansion marks ('u u -', '( - )', '(U)', '->').
- NO bare number sequences like '1 2 3 4 5 6 7 8'.
- NO English words, commentary, analysis, drafts, alternatives, markdown,
  bullets, line numbers, or explanations between the tags.
```

Ці заборони дублюють roboту sanitizer-а — модель все ще ігнорує частину з них, але явне формулювання знижує ймовірність проблем на ~60%.

## Промпт для регенерації (feedback loop)

[`NumberedLinesRegenerationPromptBuilder.build(poem, feedback_messages)`](../../src/infrastructure/prompts/regeneration_prompt_builder.py):

### Блок 1: інструкція

```
You are given a Ukrainian poem with line numbers and a list of violations.
Fix ONLY the lines mentioned in the feedback. Copy all other lines exactly
unchanged.
Return the COMPLETE poem — every line, in the correct order — with no line
numbers, no commentary, no markdown.
```

«Return the COMPLETE poem» + «no line numbers» — ключова пара: ми передамо нумерацію як візуальний натяк, але хочемо чистий вірш назад.

### Блок 2: envelope (ідентичний RAG-версії)

Той самий блок про `<POEM>…</POEM>`.

### Блок 3: строгі правила формату (коротша версія)

Ті самі заборони, що і в RAG.

### Блок 4: примітка про feedback

```
IMPORTANT: the violations below may reference stress positions and syllable
counts to explain WHAT is wrong. Do NOT copy that notation into your output.
Your output must be plain Ukrainian poem lines in normal orthography — NO
ALL-CAPS words, NO hyphenated syllables ('За-гу-бив-ся'), NO parenthesized
syllable numbers ('сло(1) во(2)'), NO scansion marks ('u u -', '(U)'), NO
bare digit sequences, NO English commentary.
```

Цей блок існує **саме тому**, що модель любить копіювати scansion з feedback-а у вивід. Повторне попередження допомагає, але не на 100%.

### Блок 5: вірш із нумерацією

```
POEM (with line numbers for reference):
1: Спинися, мить, на цім порозі,
2: Де тихо світяться вогні.
3: Замри на зоряній дорозі,
4: Навій чарівний сон мені.
```

Формат `{i+1}: {line}` — 1-based нумерація для читабельності.

### Блок 6: bullet-список порушень

```
VIOLATIONS TO FIX:
- Рядок 2: на 1 склад довше за очікуваний (ямб, 4 стопи → 8 складів)
- Пара 1–3: фонетична подібність 0.45, нижче порогу 0.7
```

Повідомлення формуються через [`UkrainianFeedbackFormatter`](../../src/infrastructure/feedback/ukrainian_formatter.py) із структурних `LineFeedback` / `PairFeedback` обʼєктів. Мова — українська (щоб модель краще розуміла українські терміни), але опис нейтральний без scansion-нотації.

## Метричні приклади — як саме підбираються

Окремий корпус [`corpus/uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) містить вірші з **розмітою метру і рими**. Кожен запис має поля `meter`, `foot_count`, `rhyme_scheme`.

[`JsonMetricRepository.find(meter, foot_count, rhyme_scheme, top_k=2)`](../../src/infrastructure/repositories/metric_repository.py):

1. Фільтрація: взяти всі записи, де одночасно збігаються `meter`, `foot_count`, `rhyme_scheme`.
2. Якщо знайшлося ≥ top_k — взяти перші top_k (за порядком у файлі; оновити на random sampling якщо треба).
3. Якщо знайшлося <top_k — взяти скільки є (може бути 0).

Немає semantic similarity — це **точний параметричний запит**. Цей корпус будується окремо через `make build-metric-corpus` який прогоняє корпус віршів через auto-detection (див. [`detection_algorithm.md`](./detection_algorithm.md)) і зберігає вірші, для яких виявлений метр і рима збігаються з тегами.

Якщо на задану комбінацію немає прикладів (рідкісна: *анапест 6-стопний AAAA*) — pipeline продовжить без блоку метричних прикладів. Це один зі сценаріїв Edge у evaluation harness (E03).

## Sanitizer-кооперація

Промпти обережно формулюють заборони, **але не розраховують на повну слухняність моделі**. Задача «чистоти виходу» розділена:

1. **Промпт** знижує ймовірність brakeage: моделі скажеш — вона спробує.
2. **Sanitizer** ловить те, що все одно просочилося. Див. [`sanitization_pipeline.md`](./sanitization_pipeline.md).

Це «ременя-і-підтяжки» підхід — ні один рівень не був надійний сам по собі.

## Ключові файли

- [`src/infrastructure/prompts/rag_prompt_builder.py`](../../src/infrastructure/prompts/rag_prompt_builder.py) — RAG-промпт для початкової генерації
- [`src/infrastructure/prompts/regeneration_prompt_builder.py`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) — промпт для регенерації з feedback
- [`src/infrastructure/feedback/ukrainian_formatter.py`](../../src/infrastructure/feedback/ukrainian_formatter.py) — форматер українських повідомлень про порушення
- [`src/infrastructure/repositories/metric_repository.py`](../../src/infrastructure/repositories/metric_repository.py) — параметричний пошук метричних прикладів
- [`src/infrastructure/llm/gemini.py`](../../src/infrastructure/llm/gemini.py) — system prompt, дублює envelope правила у `system_instruction` для Gemini API

## Тонкощі

- **System prompt для Gemini.** GeminiProvider має окремий `system_instruction` з тими ж envelope-правилами. Це не дублювання — system prompt має вищий пріоритет у Gemini API і впливає на всі виклики. User prompt (RAG/регенерація) — контекст конкретного запиту.
- **Довжина промпту.** Типовий RAG-промпт — 600-2500 символів. Виходить за 4к токенів тільки з дуже довгими тематичними прикладами (які ми не беремо).
- **Кутова точка: «do not copy».** Без цієї фрази модель часто склеює цитати з прикладів у відповідь. З нею — не ідеально, але набагато краще.
- **Рядок нумерації** у regeneration — `1: line` а не `1. line` (крапка може бути частиною справжнього рядка).
- **Текст помилок у feedback** — українською, але без scansion. Це знижує ймовірність копіювання нотації (яка у нас англійською: `u - u -`).

## Див. також

- [`semantic_retrieval.md`](./semantic_retrieval.md) — звідки приходять тематичні приклади.
- [`sanitization_pipeline.md`](./sanitization_pipeline.md) — як чиститься вивід.
- [`feedback_loop.md`](./feedback_loop.md) — як промпт регенерації вплітається у весь цикл.
- [`reliability_and_config.md`](./reliability_and_config.md) — env-параметри, що впливають на промпт (model, max_tokens, temperature).
