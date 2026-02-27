# Ukrainian Poetry Generation System — Детальний опис

> **Для кого цей документ:** розробники, дослідники, рецензенти, які хочуть зрозуміти, як система працює під капотом — від вхідного запиту до фінального вірша і метрик якості.

---

## Зміст

1. [Загальна архітектура](#1-загальна-архітектура)
2. [Компонент 1 — Корпус і завантаження даних](#2-компонент-1--корпус-і-завантаження-даних)
3. [Компонент 2 — Семантичний ретрівер (LaBSE)](#3-компонент-2--семантичний-ретрівер-labse)
4. [Компонент 3 — Побудова промпту (RAG)](#4-компонент-3--побудова-промпту-rag)
5. [Компонент 4 — LLM-клієнт (Gemini)](#5-компонент-4--llm-клієнт-gemini)
6. [Компонент 5 — Наголосовий словник (StressDict)](#6-компонент-5--наголосовий-словник-stressdict)
7. [Компонент 6 — Валідатор метру](#7-компонент-6--валідатор-метру)
8. [Компонент 7 — Валідатор рими](#8-компонент-7--валідатор-рими)
9. [Цикл генерації та перегенерації (Feedback Loop)](#9-цикл-генерації-та-перегенерації-feedback-loop)
10. [Метрики якості — формули і обґрунтування](#10-метрики-якості--формули-і-обґрунтування)
11. [Evaluation Harness і абляційні конфігурації](#11-evaluation-harness-і-абляційні-конфігурації)
12. [Сценарії тестування](#12-сценарії-тестування)
13. [Трасування пайплайну (PipelineTrace)](#13-трасування-пайплайну-pipelinetrace)
14. [Змінні середовища і налаштування](#14-змінні-середовища-і-налаштування)
15. [Діаграма потоку даних](#15-діаграма-потоку-даних)

---

## 1. Загальна архітектура

Система є **RAG-пайплайном** (Retrieval-Augmented Generation) для генерації україномовної поезії із заданими просодичними параметрами. Вона складається з п'яти послідовних етапів:

```
Вхід (тема, метр, схема рими, кількість стоп)
        │
        ▼
┌────────────────┐
│  1. Retrieval  │  ← шукає семантично близькі вірші в корпусі (LaBSE)
└────────────────┘
        │  retrieved poems
        ▼
┌────────────────┐
│  2. Prompt     │  ← будує структурований промпт з прикладами
│  Construction  │
└────────────────┘
        │  prompt string
        ▼
┌────────────────┐
│  3. Generation │  ← Gemini генерує вірш
│  (LLM)        │
└────────────────┘
        │  poem text
        ▼
┌────────────────┐
│  4. Validation │  ← перевіряє метр (по складах/наголосах) і риму
└────────────────┘
        │  ok? → повернути вірш
        │  violations? → сформувати feedback
        ▼
┌────────────────┐
│  5. Feedback   │  ← Gemini перегенеровує проблемні рядки
│  Loop          │     (до max_iterations разів)
└────────────────┘
        │
        ▼
Вихід (poem text, PipelineReport з метриками)
```

**Ключова ідея:** LLM не знає правил просодії в явному вигляді. Система компенсує це **символьною перевіркою** після генерації і **цільовим feedback** з точними позиціями помилок. Це робить підхід розширюваним: правила кодуються в `validator.py`, а не у промпті.

---

## 2. Компонент 1 — Корпус і завантаження даних

**Файл:** `src/retrieval/corpus.py`

### Структура `CorpusPoem`

```python
@dataclass(frozen=True)
class CorpusPoem:
    id: str                          # унікальний ідентифікатор
    text: str                        # повний текст вірша
    author: str | None               # автор
    approx_theme: list[str] | None   # теги теми (можуть бути None)
    source: str | None               # джерело
    lines: int | None                # кількість рядків
    embedding: list[float] | None    # попередньо обчислений LaBSE-вектор (опціонально)
```

### Джерела корпусу

| Функція | Джерело | Розмір |
|---|---|---|
| `corpus_from_env()` | `CORPUS_PATH` env → за замовчуванням `corpus/uk_poetry_corpus.json` | 53 вірші (Леся Українка та ін.) |
| `default_demo_corpus()` | хардкодні 2 вірші в коді | fallback, якщо файл не знайдено |
| `load_corpus_json(path)` | довільний JSON-файл | будь-який розмір |

### Логіка `corpus_from_env()`

```python
def corpus_from_env() -> list[CorpusPoem]:
    path = Path(os.getenv("CORPUS_PATH", "corpus/uk_poetry_corpus.json"))
    if path.exists():
        return load_corpus_json(path)
    return default_demo_corpus()   # fallback якщо файл не знайдено
```

**Навіщо це потрібно:** корпус слугує базою знань для RAG. Без реальних прикладів поетичних текстів LLM генерує без прив'язки до стилю.

### Поле `embedding` у JSON

Кожен вірш у `uk_poetry_corpus.json` має **передобчислений 768-мірний LaBSE-вектор**. Retriever використовує його напряму **без повторного кодування** при кожному запиті — це повністю усуває runtime-overhead на кодування корпусу.

Ембедінги обчислені та записані скриптом:

```bash
# Один крок: побудова корпусу + ембедінги
make build-corpus-with-embeddings

# Або лише ембедінги для існуючого корпусу (ідемпотентний — пропускає вірші з вже наявними векторами)
make embed-corpus
# python3 scripts/build_corpus_embeddings.py --corpus corpus/uk_poetry_corpus.json
```

---

## 3. Компонент 2 — Семантичний ретрівер (LaBSE)

**Файл:** `src/retrieval/retriever.py`

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

Для поточного `uk_poetry_corpus.json` крок 2б **ніколи не виконується** — всі 53 вірші мають передобчислені вектори.

### Обчислення косинусної схожості

```python
dot  = sum(a * b for a, b in zip(theme_vec, poem_vec))
norm_a = sqrt(sum(a*a for a in theme_vec))
norm_b = sqrt(sum(b*b for b in poem_vec))
sim = dot / (norm_a * norm_b)   # ∈ [-1, 1]
```

Оскільки вектори L2-нормовані (`normalize_embeddings=True`), `norm_a = norm_b = 1`, тому `sim = dot` — просто скалярний добуток.

### Fallback без LaBSE

Якщо модель не завантажилась (немає internet, помилка):

```python
# Детермінований псевдовипадковий вектор на основі хешу тексту
rng = random.Random(abs(hash(text)) % (2**32))
return [rng.gauss(0.0, 1.0) for _ in range(256)]
```

Один і той самий текст завжди дає один вектор, але **семантичного сенсу немає** — це тільки для тестів без API.

---

## 4. Компонент 3 — Побудова промпту (RAG)

**Файл:** `src/retrieval/retriever.py`, функція `build_rag_prompt()`

```python
def build_rag_prompt(
    theme, meter, rhyme_scheme, retrieved,
    stanza_count: int = 1,
    lines_per_stanza: int = 4,
) -> str:
    excerpts = "\n".join(item.text.strip() for item in retrieved)
    total_lines = stanza_count * lines_per_stanza
    structure = (
        f"{stanza_count} stanza{'s' if stanza_count > 1 else ''} "
        f"of {lines_per_stanza} lines each ({total_lines} lines total)"
    )
    return (
        "Use the following poetic excerpts as thematic inspiration (do not copy):\n"
        f"{excerpts}\n\n"
        f"Theme: {theme}\n"
        f"Meter: {meter}\n"
        f"Rhyme scheme: {rhyme_scheme}\n"
        f"Structure: {structure}\n"
        f"Generate a Ukrainian poem with exactly {total_lines} lines."
    )
```

### Структура промпту

```
Use the following poetic excerpts as thematic inspiration (do not copy):
[вірш 1 з корпусу — найближчий до теми]
[вірш 2 з корпусу]
...
[вірш 5 з корпусу]

Theme: весна у лісі, пробудження природи
Meter: ямб
Rhyme scheme: ABAB
Structure: 2 stanzas of 4 lines each (8 lines total)
Generate a Ukrainian poem with exactly 8 lines.
```

### Параметри структури

`stanza_count` і `lines_per_stanza` беруться безпосередньо з поля `EvaluationScenario` (або перевизначаються через `--stanzas`/`--lines-per-stanza` CLI / Makefile). Добуток `stanza_count × lines_per_stanza` = `total_lines` передається LLM як жорстка вимога.

**Навіщо "do not copy":** без цієї вказівки LLM може буквально відтворити вірш із корпусу. Нас цікавить тематичне натхнення, а не копіювання.

**Системна інструкція** передається окремо через `system_instruction` у `GeminiLLMClient`:
```
You are a Ukrainian poetry generator. Return only the poem text, no explanations, no markdown.
```

Це дає LLM чіткий контекст ролі і усуває зайвий текст у відповіді (коментарі, пояснення, markdown-форматування).

---

## 5. Компонент 4 — LLM-клієнт (Gemini)

**Файл:** `src/generation/llm.py`

### Абстракція `LLMClient`

```python
class LLMClient(ABC):
    def generate(self, prompt: str) -> LLMResult: ...
    def regenerate_lines(self, poem_text: str, feedback: list[str]) -> LLMResult: ...
```

Дві операції:
- **`generate`** — перша генерація з RAG-промптом
- **`regenerate_lines`** — перегенерація з поемою і списком порушень

### `GeminiLLMClient` — реальний клієнт

Використовує **новий `google.genai` SDK** (не deprecated `google.generativeai`):

```python
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.9,          # висока: більше творчості
        max_output_tokens=4096,   # достатньо для 4-строфного вірша
        system_instruction=...,
    ),
)
```

**Параметри:**
- `temperature=0.9` — відносно висока, щоб генерація була варіативною і не повторювала однакові рядки
- `max_output_tokens=4096` — 1024 раніше призводило до обрізаних віршів; збільшено до 4096
- `model="gemini-2.0-flash"` — актуальна модель (не `gemini-3.1-pro`, якої не існує)

### `MockLLMClient` — заглушка для тестів

Повертає фіксований вірш без API-запиту. При `regenerate_lines` імітує виправлення, переставляючи слова у рядках з порушеннями:

```python
# Міняє місцями два останні слова в проблемному рядку
words[-1], words[-2] = words[-2], words[-1]
```

Це дозволяє тестувати пайплайн без витрат API-квоти.

### `llm_from_env()`

```python
def llm_from_env() -> LLMClient | None:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    model = os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"
    temperature = float(os.getenv("GEMINI_TEMPERATURE") or "0.9")
    max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS") or "4096")
    return GeminiLLMClient(api_key, model, temperature, max_output_tokens)
```

Якщо `GEMINI_API_KEY` не встановлено — повертає `None`, і `run_full_pipeline` автоматично падає на `MockLLMClient`.

---

## 6. Компонент 5 — Наголосовий словник (StressDict)

**Файл:** `src/meter/stress.py`

### Навіщо він потрібен

Щоб перевірити метр вірша, потрібно знати **на який склад падає наголос у кожному слові**. В українській мові наголос вільний (немає фіксованого правила), тому потрібен зовнішній ресурс.

### Реалізація

```python
@dataclass
class StressDict:
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

### Fallback `get_stress_index_safe(word, stress_dict) → int`

```python
def get_stress_index_safe(word, stress_dict) -> int:
    idx = stress_dict.get_stress_index(word)
    if idx is not None:
        return idx
    syllables = count_syllables_ua(word)
    return max(0, syllables - 1)   # наголос на останньому складі
```

Якщо `_stressify` недоступний або слово не розпізнане — **наголос ставиться на останній склад** (умовний fallback).

---

## 7. Компонент 6 — Валідатор метру

**Файл:** `src/meter/validator.py`

### Підтримувані метри

```python
_METER_TEMPLATES = {
    "ямб":        ["u", "—"],       # нАголос на парній складі
    "хорей":      ["—", "u"],       # нАголос на непарній
    "дактиль":    ["—", "u", "u"],  # трискладова стопа
    "амфібрахій": ["u", "—", "u"],
    "анапест":    ["u", "u", "—"],
}
```

`"—"` = наголошена позиція, `"u"` = ненаголошена.

### Алгоритм `check_meter_line(line, meter, foot_count)`

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
Для кожного слова: знаходимо наголос через `StressDict`, ставимо `"—"` на відповідну позицію у загальному масиві складів, решта — `"u"`.

```
"Весна  прийшла  у  ліс  зелений"
  2сл    3сл    1сл 1сл    3сл      ← syllables_per_word
  [u,—]  [u,—,u] [u] [—]  [u,—,u]  ← actual stress positions
→ actual = [u,—, u,—,u, u, —, u,—,u]
```

**Крок 4 — Порівняння:**
```python
n = min(len(actual), len(expected))
errors = [i+1 for i in range(n) if actual[i] != expected[i]]
ok = len(errors) <= allowed_mismatches and len(actual) == len(expected)
```

**Допустиме відхилення `allowed_mismatches=2`:** реальна поезія дозволяє незначні ритмічні відступи. Рядок вважається **правильним**, якщо не більше 2 позицій не збігаються і загальна кількість складів відповідає очікуваній.

### Метрика Meter Accuracy

```
meter_accuracy = (кількість рядків з ok=True) / (загальна кількість рядків)
```

Рахується окремо для кожного рядка вірша. Значення `1.0` = всі рядки відповідають метру.

---

## 8. Компонент 7 — Валідатор рими

**Файл:** `src/rhyme/validator.py`, `src/rhyme/transcribe.py`

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
# src/rhyme/transcribe.py
_UA_MAP = {"а":"a", "б":"b", "г":"ɦ", "ж":"ʒ", "и":"ɪ", "і":"i", ...}

def transcribe_ua(word: str) -> str:
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
# src/utils/distance.py
def normalized_similarity(a: str, b: str) -> float:
    d = levenshtein_distance(a, b)
    return 1.0 - d / max(len(a), len(b))
```

Відстань Левенштейна рахує мінімальну кількість операцій (вставка, видалення, заміна) для перетворення `a` в `b`. Нормалізована схожість = `1 - d/max_len` ∈ [0, 1].

**Поріг:** рима вважається **правильною**, якщо `score >= 0.7`. Це дозволяє приймати неточні рими (`"ɪj"` vs `"ij"` → відстань 1 з 3 → score ~0.67 — не ок; `"ɪt"` vs `"ɪt"` → відстань 0 → score 1.0 — ок).

### Метрика Rhyme Accuracy

```
rhyme_accuracy = (кількість пар з rhyme_ok=True) / (загальна кількість пар)
```

Для ABAB з 4 рядками — 2 пари: (0,2) і (1,3). Якщо одна пара рима — `0.5`.

---

## 9. Цикл генерації та перегенерації (Feedback Loop)

**Файл:** `src/pipeline/full_system.py`

### Покроковий процес

```
┌───────────────────────────────────────────────────────────────────────┐
│ run_full_pipeline(theme, meter, rhyme_scheme, foot_count,             │
│                   stanza_count=1, lines_per_stanza=4, ...)            │
└───────────────────────────────────────────────────────────────────────┘
         │
         ▼
[1] corpus_from_env()           → завантажити корпус (53 вірші або demo)
[2] retriever.retrieve(theme)   → top-5 семантично близьких віршів
                                  (використовує pre-computed embeddings)
[3] build_rag_prompt(...)       → зібрати промпт з прикладами і параметрами
                                  включаючи stanza_count × lines_per_stanza
[4] llm.generate(prompt)        → Gemini генерує перший вірш

[5] check_poem(poem) →
      check_meter_poem()  → перевірити кожен рядок по складах/наголосах
      check_rhyme()       → перевірити пари рядків на рифму

[6] Якщо meter_ok AND rhyme_ok → ✅ ГОТОВО, повернути вірш

[7] Якщо є порушення:
    → meter_feedback() для кожного рядка з порушенням метру
    → rhyme_feedback() для кожної пари з поганою римою
    → prev_poem = poem
    → llm.regenerate_lines(poem, feedback)  → Gemini виправляє
    → merge_regenerated_poem(prev_poem, regen, feedback)
         ↑ safety guard: якщо LLM повернув < рядків — відновлює повний вірш

[8] check_poem(повний вірш) → метрики рахуються ЗАВЖДИ на повному вірші
    (максимум max_iterations=1 раз за замовчуванням)

[9] Повернути фінальний вірш + PipelineReport
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

### Що повертає `PipelineReport`

```python
@dataclass(frozen=True)
class PipelineReport:
    meter_ok: bool           # всі рядки відповідають метру
    rhyme_ok: bool           # всі пари рими правильні
    meter_accuracy: float    # частка правильних рядків [0,1]
    rhyme_accuracy: float    # частка правильних пар рими [0,1]
    feedback: list[str]      # список повідомлень про порушення (фінальний стан)
    iterations: int          # скільки ітерацій feedback loop було використано
```

---

## 10. Метрики якості — формули і обґрунтування

**Файл:** `src/evaluation/metrics.py`

### 10.1 Meter Accuracy

```
meter_accuracy = Σ(рядок_i.ok) / N_рядків
```

Де `рядок_i.ok = True` якщо кількість невідповідних наголосів ≤ `allowed_mismatches=2` **і** загальна кількість складів збігається.

**Обґрунтування порогу 2:** класична поезія допускає **ритмічні варіації** (pyrrhic, spondee). Строге правило `≤0 mismatches` відкидало б валідні рядки.

### 10.2 Rhyme Accuracy

```
rhyme_accuracy = Σ(пара_i.rhyme_ok) / N_пар
```

Де `пара_i.rhyme_ok = True` якщо `normalized_similarity(rhyme_part_1, rhyme_part_2) ≥ 0.7`.

**Обґрунтування порогу 0.7:** рима не завжди точна (чоловіча/жіноча, тощо). Поріг 0.7 відповідає приблизно 1-2 символам різниці в IPA — прийнятна неточна рима. Нижче 0.7 — суттєве розходження.

### 10.3 Regeneration Success Rate

```
success_rate = (meter_violations_fixed + rhyme_violations_fixed) /
               (initial_meter_violations + initial_rhyme_violations)
```

Показує, яку частку порушень вдалося виправити через feedback loop. Значення `1.0` = всі порушення виправлені, `0.0` = нічого не покращилось.

**Навіщо:** ця метрика вимірює **ефективність feedback** незалежно від початкової якості LLM. Навіть якщо вірш починається поганим (низький meter/rhyme accuracy), високий success rate означає що система вміє виправляти.

### 10.4 BLEU (Bilingual Evaluation Understudy)

```python
BLEU = BP × exp(Σ weight_n × log(precision_n))
```

де:
- `precision_n` = частка n-грам кандидата, що є у reference (з обрізанням за частотою)
- `BP` (brevity penalty) = `min(1, exp(1 - |ref|/|cand|))` — штраф за короткий кандидат
- `weight_n = 1/4` для n=1..4

**Реалізація:** власна, без зовнішніх бібліотек (NLTK). Токенізація через regex `[а-яіїєґa-z'ʼ-]+`.

**Навіщо BLEU:** стандартна метрика машинного перекладу і генерації. Оцінює **лексичний збіг** між згенерованим і референсним текстом. Корисна коли є еталонний вірш на ту саму тему.

**Обмеження:** BLEU не враховує порядок речень і семантику. Два семантично ідентичних тексти з різною лексикою можуть мати BLEU ≈ 0.

### 10.5 ROUGE-L (Recall-Oriented Understudy for Gisting Evaluation)

```
LCS = найдовша спільна підпослідовність токенів
precision = LCS / |candidate|
recall    = LCS / |reference|
ROUGE-L   = 2 × precision × recall / (precision + recall)   [F1-міра]
```

**Реалізація:** власний динамічний алгоритм LCS за O(m×n) без зовнішніх залежностей.

**Чому ROUGE-L, а не ROUGE-1/2:** LCS враховує **порядок слів** (хоча й не вимагає суміжності), тому краще відображає структурну схожість поетичних текстів ніж просте bag-of-words перекриття n-грам.

### 10.6 BERTScore (опціональний)

```
precision = mean_i(max_j sim(c_i, r_j))
recall    = mean_j(max_i sim(c_i, r_j))
BERTScore = F1(precision, recall)
```

де `sim` — косинусна схожість між contextual embeddings токенів.

Використовує `bert-base-multilingual-cased`. Вмикається прапором `compute_bertscore=True`. **Повільний** (завантажує ~700MB модель), тому за замовчуванням вимкнений.

---

## 11. Evaluation Harness і абляційні конфігурації

**Файли:** `src/evaluation/runner.py`, `scripts/run_evaluation.py`

### Абляційні конфігурації

| Config | Retrieval | Validation | Feedback | Призначення |
|--------|-----------|------------|----------|-------------|
| **A** | ❌ | ❌ | ❌ | Baseline: чистий LLM без підтримки |
| **B** | ❌ | ✅ | ❌ | LLM + вимірювання якості, без виправлень |
| **C** | ❌ | ✅ | ✅ | LLM + повний feedback loop, без RAG |
| **D** | ✅ | ✅ | ✅ | **Повна система** |
| **E** | ❌ | ✅ | ✅ | Як C (явно без retrieval, для порівняння) |

**Навіщо абляції:** порівнюючи A vs B vs C vs D можна кількісно виміряти внесок кожного компонента. Наприклад:
- `D.meter_accuracy - C.meter_accuracy` → скільки дає RAG для метру
- `C.meter_accuracy - B.meter_accuracy` → скільки дає feedback loop

### Матриця оцінки

```python
run_evaluation_matrix(
    scenarios=[...],    # N сценаріїв
    configs=[...],      # M конфігурацій
)
# → N × M трасів + таблиця підсумків
```

### Запуск

```bash
# Один сценарій, одна конфігурація, детальний вивід
make evaluate SCENARIO=N01 CONFIG=D VERBOSE=1

# Всі normal сценарії, конфіг C
make evaluate CATEGORY=normal CONFIG=C

# З кастомним корпусом і збереженням результатів
CORPUS_PATH=my_corpus.json make evaluate OUTPUT=results/run1.json

# Перевизначити структуру вірша для всіх сценаріїв
make evaluate STANZAS=3 LINES_PER_STANZA=6

# Один сценарій з кастомною структурою
make evaluate SCENARIO=N01 CONFIG=D STANZAS=2 LINES_PER_STANZA=6
```

Параметри `STANZAS` і `LINES_PER_STANZA` (Makefile) або `--stanzas`/`--lines-per-stanza` (CLI) застосовуються до всіх обраних сценаріїв через `dataclasses.replace()` — оригінальні об'єкти не змінюються.

### Makefile-змінні для evaluation

| Змінна | За замовчуванням | Опис |
|--------|-----------------|------|
| `SCENARIO` | *(всі)* | ID сценарію: `N01`–`N05`, `E01`–`E05`, `C01`–`C08` |
| `CONFIG` | *(всі)* | Абляційна конфіг: `A`, `B`, `C`, `D`, або `E` |
| `CATEGORY` | *(всі)* | Фільтр: `normal`, `edge`, або `corner` |
| `VERBOSE` | *(вимк.)* | `1` для повних stage-by-stage трасів |
| `OUTPUT` | `results/evaluation.json` | Шлях для збереження JSON |
| `STANZAS` | `2` | Перевизначити кількість строф |
| `LINES_PER_STANZA` | `4` | Перевизначити рядків на строфу |

---

## 12. Сценарії тестування

**Файл:** `src/evaluation/scenarios.py`

18 кюрованих сценаріїв у трьох категоріях. Кожен сценарій визначає параметри структури вірша:

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

Ці значення автоматично передаються в `build_rag_prompt()` і визначають розмір вірша, який LLM має згенерувати. Можна перевизначити через `--stanzas`/`--lines-per-stanza` або `STANZAS`/`LINES_PER_STANZA` у Makefile.

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
| C01 | порожня тема `""` | graceful handling |
| C02 | тема >200 символів | довгий промпт |
| C03 | тема англійською | cross-language retrieval |
| C04 | метр `"гекзаметр"` (невідомий) | помилка валідатора |
| C05 | `foot_count=1` | екстремальний мінімум |
| C06 | emoji + HTML у темі | sanitization |
| C07 | мікс укр+рос | мовна консистентність виходу |
| C08 | `foot_count=0` | нуль (degenerate input) |

---

## 13. Трасування пайплайну (PipelineTrace)

**Файли:** `src/evaluation/trace.py`, `src/evaluation/runner.py`

Кожен запуск в evaluation harness записує повний `PipelineTrace`:

```python
PipelineTrace
├── scenario_id: str              # "N01"
├── config_label: str             # "D"
├── stages: list[StageRecord]     # один запис на кожен етап
│   ├── name                      # "retrieval", "prompt_construction", ...
│   ├── input_summary             # коротко: "theme='весна', corpus_size=53"
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
├── final_metrics: dict           # meter_accuracy, rhyme_accuracy, bleu, rouge_l, ...
├── total_duration_sec: float
└── error: str | None
```

Трас серіалізується в JSON через `trace.to_dict()` і зберігається якщо передати `--output results/eval.json`.

---

## 14. Змінні середовища і налаштування

### Runtime (env vars)

| Змінна | За замовчуванням | Опис |
|--------|-----------------|------|
| `GEMINI_API_KEY` або `GOOGLE_API_KEY` | — | API-ключ Gemini (обов'язково для реальної генерації) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Назва моделі |
| `GEMINI_TEMPERATURE` | `0.9` | Температура генерації |
| `GEMINI_MAX_OUTPUT_TOKENS` | `4096` | Ліміт токенів виводу |
| `CORPUS_PATH` | `corpus/uk_poetry_corpus.json` | Шлях до JSON-файлу корпусу |

### Corpus management (Makefile)

| Змінна | За замовчуванням | Опис |
|--------|-----------------|------|
| `DATA_DIR` | `data` | Директорія з `.txt`-файлами віршів |
| `OUT` | `corpus/uk_poetry_corpus.json` | Вихідний JSON-файл корпусу |
| `MIN_COUNT` | `1` | Мінімальна кількість віршів |
| `CORPUS` | `corpus/uk_poetry_corpus.json` | Шлях для `embed-corpus` |

Без `GEMINI_API_KEY` система автоматично використовує `MockLLMClient` — достатньо для запуску тестів і перевірки структури пайплайну.

---

## 15. Діаграма потоку даних

```
КОРПУС (corpus/uk_poetry_corpus.json)
  53 вірші + pre-computed LaBSE embeddings [768-dim]
        │
        │ corpus_from_env()  (або CORPUS_PATH env var)
        ▼
  ┌─────────────┐     encode(theme) via LaBSE 768-dim
  │ SemanticRe- │ ◄───────────────────────────────────── USER INPUT
  │  triever    │  poem.embedding → без on-the-fly кодування  (theme, meter,
  └─────────────┘                                              rhyme_scheme,
        │ top_k RetrievalItem                                  foot_count,
        │ {poem_id, text, similarity}                          stanza_count,
        ▼                                                      lines_per_stanza)
  ┌─────────────┐                                              │
  │ build_rag_  │ ◄────────────────────────────────────────────┘
  │   prompt()  │  Structure: NxM lines total
  └─────────────┘
        │ prompt string (~500-2000 chars)
        ▼
  ┌─────────────┐     GEMINI API
  │ GeminiLLM   │ ──────────────► generate_content()
  │  Client     │ ◄──────────────  poem text (full poem)
  └─────────────┘
        │
        ▼
  ┌─────────────┐     StressDict (ukrainian-word-stress + Stanza)
  │ check_meter │ ──► per-line stress pattern comparison
  │   _poem()   │     → list[MeterCheckResult]
  └─────────────┘
        │
  ┌─────────────┐     rhyme_part_from_stress() → IPA
  │ check_rhyme │ ──► normalized_similarity() → Levenshtein
  │    ()       │     → RhymeCheckResult
  └─────────────┘
        │
        ├── ALL OK? ──────────────────────────────► RETURN poem
        │
        │ violations → feedback messages
        ▼
  ┌─────────────┐     GEMINI API
  │ GeminiLLM   │ ──────────────► regenerate_lines() [numbered poem + violations]
  │  .regen...  │ ◄──────────────  revised full poem
  └─────────────┘
        │
  ┌─────────────┐
  │   merge_    │ ── safety guard: якщо LLM повернув < рядків →
  │ regen_poem()│    підставляє нові рядки в оригінал за feedback-індексами
  └─────────────┘
        │
        └── check_poem() на ПОВНОМУ вірші → (повтор, max_iterations разів)
                    │
                    ▼
             RETURN (poem, PipelineReport)
```

---

*Актуальний для версії: `src/pipeline/full_system.py`, `src/generation/llm.py`, `src/evaluation/`, `src/meter/`, `src/rhyme/`, `src/retrieval/`, `scripts/build_corpus_embeddings.py`.*
