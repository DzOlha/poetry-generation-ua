# Алгоритм детекції метру та схеми римування / Detection Algorithm

## Загальний потік / General Flow

```
Текст вірша
    │
    ├─ HTTP-вхід: api.routers.detection / web.routes.detection
    │      обидва інжектять DetectionService + IMeterValidator + PoetryService
    │      через Depends(get_detection_service / get_meter_validator / get_poetry_service)
    │
    ├─ detect_orchestrator.detect_poem(...)
    │      1. Валідація запиту (хоч одна опція? непорожній? кратність 4 для рими?)
    │      2. DetectionService.detect(poem_text, sample_lines=4) — повний прохід
    │      3. Розбиття на строфи (split_stanzas: порожні рядки або по 4)
    │      4. Per-stanza fallback метру (full-poem → per-stanza → best-guess)
    │      5. Перевалідація строф → анотовані `line_displays`
    │
    └─ DetectionService.detect (services.detection_service)
           sampler.sample(poem_text, n_lines) → потрібно ≥ default_sample_lines
           meter_detector.detect(poem_text)   → BruteForceMeterDetector
           rhyme_detector.detect(poem_text)   → BruteForceRhymeDetector
           повертає DetectionResult(meter: MeterDetection?, rhyme: RhymeDetection?)
```

`DetectionResult.meter` і `.rhyme` — **`None`**, коли нічого не знайдено; схеми / шаблони рендерять це як «не визначено», а не маскують дефолтом.

---

## Конструктор DetectionService

`DetectionService` більше не приймає обʼєкт `DetectionConfig`. Поточний контракт:

```python
class DetectionService(IDetectionService):
    def __init__(
        self,
        sampler: IStanzaSampler,
        meter_detector: IMeterDetector,
        rhyme_detector: IRhymeDetector,
        default_sample_lines: int,   # просте число, не config-структура
        logger: ILogger,
    ) -> None: ...
```

`default_sample_lines` — мінімальна кількість рядків, нижче якої детекція пропускається (повертає `DetectionResult(meter=None, rhyme=None)` і логує "Poem too short for detection"). Brute-force детектори зберігають свою власну референцію на `DetectionConfig` для порогів і діапазону стопностей; сервіс — ні.

`FirstLinesStanzaSampler.sample(poem_text, line_count)` повертає перші `line_count` непорожніх рядків (склеєних `\n`) або `None`, якщо вірш коротший. Дефолт `4` природний для пошуку по чотиривіршу.

---

## 1. Детекція метру / Meter Detection

### 1.1 Brute-force перебір

**Файл:** [`src/infrastructure/detection/brute_force_meter_detector.py`](../../src/infrastructure/detection/brute_force_meter_detector.py)

Алгоритм перебирає всі комбінації метру та кількості стоп:

| Метр | Шаблон стопи |
|------|-------------|
| Ямб (iamb) | `u —` |
| Хорей (trochee) | `— u` |
| Дактиль (dactyl) | `— u u` |
| Амфібрахій (amphibrach) | `u — u` |
| Анапест (anapest) | `u u —` |

- Кількість стоп: `feet_min` … `feet_max` (дефолти `1` … `6` — узгоджено з межами генерації / валідації, щоб система могла розпізнати будь-який вірш, який вона сама вміє згенерувати)
- Для кожної комбінації запускається ін'єктований `IMeterValidator.validate(text, MeterSpec)` — за замовчуванням `PatternMeterValidator`
- Кандидат проходить попередній фільтр, якщо `accuracy ≥ meter_min_accuracy` (дефолт 0.85)
- **Tie-break:** серед усіх, що пройшли, обирається кандидат із найбільшим кортежем `(accuracy, -total_errors)`, де `total_errors = sum(len(line.error_positions))` по всіх `LineMeterResult` повернутого `MeterResult`. Семантика: при рівній accuracy виграє кандидат із меншою сумарною кількістю реальних помилок. Без цього кроку перемагав би перший за порядком ітерації — і коротший метр з ліберальною толерантністю довжини «крав» би перемогу у довшого, який пасує точно (див. приклад у §1.3).

### 1.2 Валідація рядка метру

**Файл:** [`src/infrastructure/validators/meter/pattern_validator.py`](../../src/infrastructure/validators/meter/pattern_validator.py)

Детектор використовує **`PatternMeterValidator`** — той самий валідатор, що й генераційний пайплайн. Емпіричний прогон по [`uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) (193 записи) підтвердив, що він добре калібрований для детекції на сучасному українському корпусі і не відкидає рядків класиків (Шевченко, Рильський, Антонич) через суто позиційні відхилення.

Для кожного рядка вірша:

1. **Токенізація:** розбиття на слова, підрахунок складів (кількість голосних).
2. **Очікуваний паттерн:** шаблон стопи × кількість стоп (наприклад, ямб 4-стопний = `u—u—u—u—`).
3. **Фактичний паттерн:** визначення наголосу для кожного слова (див. розділ 3).
4. **Порівняння:** знаходження розбіжностей між фактичним і очікуваним.
5. **Толерантність:** деякі розбіжності прощаються — пірихії, спондеї, каталектика на короткий хвіст (див. розділ 4).
6. **Рішення:** рядок проходить, якщо `len(real_errors) <= allowed_mismatches` (дефолт 2) І довжина OK.
7. **Експорт:** `error_positions` записується у `LineMeterResult` — саме його сумарна довжина по всіх рядках і є tie-break сигналом для детектора. Tie-break за `error_positions` дає очікуваний ефект «точніший fit виграє» без втрат на довших метрах.

### 1.3 Приклад: чому tie-break критичний

Вірш у дактилі 2-ст.:
```
Крапля скотилася    → [—, u, u, —, u, u]
Голка по шибочках   → [—, u, u, —, u, u]
Тихо відбилася      → [—, u, u, —, u, u]
Казка у кутиках     → [—, u, u, —, u, u]
```

Реальний прогон детектора:

| Метр (2-ст.) | Очікуваний патерн | Помилки на рядок | length_ok | accuracy |
|--------------|--------------------|-------------------|-----------|----------|
| **Ямб** | `[u, —, u, —]` (4 склади) | 2 (на грані `allowed_mismatches=2`) | ✓ (через толерантність +2 ненаголошених) | **1.00** |
| **Дактиль** | `[—, u, u, —, u, u]` (6 складів) | **0** | ✓ (точна довжина) | **1.00** |

Обидва метри проходять при accuracy = 1.00 — ямб «тягнеться» лише через ліберальну толерантність довжини +2 ненаголошених у хвості ([`prosody.py:79-80`](../../src/infrastructure/validators/meter/prosody.py#L79-L80)) плюс рівно `allowed_mismatches` помилок. Без tie-break перший за порядком ітерації (ямб у [`brute_force_meter_detector.py:17-23`](../../src/infrastructure/detection/brute_force_meter_detector.py#L17-L23)) виграв би. Tie-break за сумою `error_positions` (8 для ямба × 4 рядки = `total_errors=8` vs дактиль `total_errors=0`) коректно обирає дактиль.

### 1.4 Емпірична верифікація

Логіку tie-break запровадили після того, як обидві стратегії — legacy (тільки `accuracy`) та current (`(accuracy, -total_errors)`) — прогнали по 193-записному корпусу [`uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) і порівняли з анотацією. На момент впровадження tie-break:

| Стратегія | `meter+feet` збігається з корпусом | Без детекції |
|-----------|-------------------------------------|--------------|
| legacy | 161/193 (83%) | 19 |
| **current (tie-break)** | **170/193 (88%)** | 19 |

9 чистих виграшів, 0 регресій. Решта 23 розбіжностей залишаються як були — це окреме питання (стрес-резолвер на довгих метрах, поріг 0.85, силабо-тонічна непослідовність XVIII ст.).

### 1.5 Толерантність довжини рядка

**Файл:** [`src/infrastructure/validators/meter/prosody.py`](../../src/infrastructure/validators/meter/prosody.py), метод `line_length_ok`

| Різниця (факт - очікув) | Рішення | Пояснення |
|--------------------------|---------|-----------|
| 0 | OK | Точний збіг |
| +1, останній = "u" | OK | Жіноча клаузула |
| +2, останні = "uu" | OK | Дактилічна клаузула |
| -1..-foot_size, обрізані "u" | OK | Каталектика |
| інше | FAIL | |

---

## 2. Детекція рими / Rhyme Detection

### 2.1 Brute-force перебір

**Файл:** `src/infrastructure/detection/brute_force_rhyme_detector.py`

Перебирає чотири схеми у порядку: **AAAA, ABAB, AABB, ABBA**. AAAA — перша свідомо: вона найсуворіша (кожна пара має римуватися). На чотиривірші слабші схеми проходять разом з AAAA, тож без цього порядку моноримию мовчки видавали б за ABAB.

Поріг accuracy `rhyme_min_accuracy` (дефолт 0.5). При 4 рядках є лише 2 пари, тому accuracy ∈ {0.0, 0.5, 1.0}.

### 2.2 Побудова пар для римування

**Файл:** `src/infrastructure/validators/rhyme/scheme_extractor.py`

Схема римування трактується як шаблон строфи та повторюється по всіх строфах:

```
Схема ABAB, 8 рядків:
  Строфа 1: пари (0,2), (1,3)
  Строфа 2: пари (4,6), (5,7)
  
Неповна остання строфа ігнорується.
```

### 2.3 Аналіз пари рим

**Файл:** `src/infrastructure/validators/rhyme/pair_analyzer.py`

1. Для кожного слова визначається наголос
2. Від наголошеного голосного до кінця — "римувальна частина" (rhyme part)
3. Слова транскрибуються в IPA (МФА)
4. Римувальні частини вирівнюються по суфіксу та порівнюються через відстань Левенштейна
5. `score = 1 - (edit_distance / max_length)`
6. Пара вважається римою, якщо score >= 0.55

### 2.4 Класифікація точності рими

| Score | Тип | Опис |
|-------|-----|------|
| >= 0.95 | EXACT | Точна рима |
| голосні >= 0.75, приголосні < 0.75 | ASSONANCE | Асонанс |
| приголосні >= 0.75, голосні < 0.75 | CONSONANCE | Консонанс |
| > 0.0 | INEXACT | Неточна рима |
| 0.0 | NONE | Не рима |

---

## 3. Визначення наголосу / Stress Resolution

**Файл:** `src/infrastructure/stress/penultimate_resolver.py`

### 3.1 Ієрархія

1. **Словник** (`ukrainian-word-stress`): пайплайн Stanza від Stanford NLP (українські моделі, ~500 МБ) — морфологічний аналіз + пошук наголосу
2. **Евристика** (fallback): якщо словник повертає `None`

### 3.2 Евристика наголосу

Заснована на дослідженні дефолтного наголосу в слов'янських мовах
(Dolatian & Guekguezian, Cambridge Phonology 2019):

| Закінчення слова | Наголос | Приклади |
|-----------------|---------|----------|
| Голосна (а, е, і, о, у, ю, я, є, ї, и) | Передостанній склад | стóгне, кохáння, укрáїна |
| «й» або «ь» | Передостанній склад | ширóкий, зелéний, мíсяць |
| Тверда приголосна (р, н, т, с, ...) | Останній склад | горúть, вітéр |
| 1 склад | Єдиний склад | ліс, Дніпр |

Точність на тестовій вибірці: ~79%.

### 3.3 Синглтон моделі

**Файл:** `src/infrastructure/stress/ukrainian.py`

Моделі Stanza (~500 МБ при першому завантаженні) кешуються на рівні модуля
(thread-safe singleton), щоб кілька контейнерів не дублювали їх у пам'яті.

---

## 4. Службові слова / Weak Stress Words

**Файл:** `src/infrastructure/meter/ukrainian_weak_stress_lexicon.py`

### 4.1 Вплив на паттерн наголосів

Односкладові службові слова ("і", "до", "як", "бо", "та", "не"...)
**не отримують наголос** у фактичному паттерні — вони позначаються як "u" (ненаголошені).

Багатоскладові службові слова ("твої", "вона", "якщо"...)
отримують наголос нормально, але розбіжності з очікуваним паттерном **прощаються**.

### 4.2 Правила толерантності

**Файл:** `src/infrastructure/validators/meter/prosody.py`, метод `is_tolerated_mismatch`

Розбіжність на позиції прощається, якщо:
- Слово на цій позиції **односкладове** (спондей/піріхій для повнозначного слова), АБО
- Слово на цій позиції **службове** (weak stress word)

---

## 5. Оркестрація: per-stanza логіка / Stanza-level UI Logic

**Файли:** `src/handlers/shared/detect_orchestrator.py`, `src/handlers/api/routers/detection.py`, `src/handlers/web/routes/detection.py`

HTML- і JSON-API-handler-и поділяють спільний `detect_orchestrator.detect_poem(...)`, тож обидві поверхні повертають однакові факти детекції. Обидва маршрути інжектять залежності через FastAPI `Depends`:

```python
service: DetectionService     = Depends(get_detection_service)
poetry: PoetryService         = Depends(get_poetry_service)
meter_validator: IMeterValidator = Depends(get_meter_validator)
```

Це замінило старі module-level singleton-и; тести можуть перепризначити будь-яку залежність через `app.dependency_overrides`.

### 5.1 Розбиття на строфи

`split_stanzas(poem_text, stanza_size=4)`:
1. Якщо є порожні рядки між строфами — розбиття по них.
2. Якщо порожніх роздільників немає — fallback до фіксованих чанків по 4 рядки (тільки якщо всього > 4 рядків; інакше вірш залишається одним блоком).
3. Для рими оркестратор додатково вимагає кратність 4 — інакше запит відхиляється з україномовним повідомленням ще до запуску детекторів.

### 5.2 Три рівні fallback для метру кожної строфи

1. **Full-poem detection** (`DetectionService.detect`, поріг ≥ `meter_min_accuracy`).
2. **Per-stanza detection** (`DetectionService.detect(stanza_text, sample_lines=STANZA_SIZE)`).
3. **Best-guess** (`_best_guess_meter`: найвищий accuracy > 0, без порога) — лише для підсвічування.

### 5.3 Структура per-stanza відповіді

Кожна строфа перевалідовується через `PoetryService.validate(...)` для отримання char-level стрес-сегментів через `handlers.shared.line_displays.line_displays`. Обидва маршрути повертають per-stanza дані:

| Поле | Значення |
|------|----------|
| `meter` | `MeterDetection?` для строфи |
| `rhyme` | `RhymeDetection?` для строфи |
| `meter_accuracy` / `rhyme_accuracy` | accuracy з локального проходу валідації |
| `lines_count` | кількість рядків у строфі |
| `line_displays` | char-level стрес-сегменти — те, що SPA / Jinja-шаблони використовують для підсвічування |

API повертає `StanzaDetectionSchema` (див. `src/handlers/api/schemas.py`); web-handler рендерить ті самі дані в Jinja-шаблони.

### 5.4 Чекбокси в UI

- Можна обрати "Метр", "Схема римування", або обидва
- Лише метр: приймається будь-яка кількість рядків
- Схема римування: кількість рядків має бути кратною 4

### 5.5 Обробка помилок

Помилки мапляться поліморфно через [`DefaultHttpErrorMapper`](../../src/infrastructure/http/error_mapper.py): кожен підклас `DomainError` несе власний `http_status_code` (наприклад, `UnsupportedConfigError` → 422, `EmbedderError` → 503, `LLMError` → 502). Маппер просто читає `exc.http_status_code` без `isinstance`-розгалужень — нові типи помилок не вимагають правок мапера.

---

## 6. Порогові значення / Thresholds Summary

| Компонент | Поріг | Значення | Файл |
|-----------|-------|----------|------|
| Детекція метру | min accuracy | 0.85 | config.py |
| Детекція рими | min accuracy | 0.5 | config.py |
| Валідація метру (per-line) | allowed mismatches | 2 | config.py |
| Валідація рими (per-pair) | similarity score | 0.55 | phonetic_validator.py |
| Точна рима | score | >= 0.95 | pair_analyzer.py |
| Асонанс/Консонанс | channel score | >= 0.75 | pair_analyzer.py |
| Стопність | feet range | 1-6 | config.py |
| Розмір строфи | stanza size | 4 (фіксований) | config.py |

---

## 7. Ключові файли / Key Files

| Що | Файл |
|----|------|
| Web route (форма → детекція) | `src/handlers/web/routes/detection.py` |
| API route (JSON-детекція) | `src/handlers/api/routers/detection.py` |
| Спільний оркестратор | `src/handlers/shared/detect_orchestrator.py` |
| FastAPI-залежності | `src/handlers/api/dependencies.py` (`get_detection_service`, `get_meter_validator`, `get_poetry_service`) |
| Сервіс детекції | `src/services/detection_service.py` |
| Сэмплер строф | `src/infrastructure/detection/stanza_sampler.py` (`FirstLinesStanzaSampler`) |
| Детектор метру (brute-force) | `src/infrastructure/detection/brute_force_meter_detector.py` |
| Детектор рими (brute-force) | `src/infrastructure/detection/brute_force_rhyme_detector.py` |
| Валідатор метру | `src/infrastructure/validators/meter/pattern_validator.py` |
| Просодичний аналізатор | `src/infrastructure/validators/meter/prosody.py` |
| Валідатор рими | `src/infrastructure/validators/rhyme/phonetic_validator.py` |
| Екстрактор схеми рим | `src/infrastructure/validators/rhyme/scheme_extractor.py` |
| Аналізатор пари рим | `src/infrastructure/validators/rhyme/pair_analyzer.py` |
| Резолвер наголосу | `src/infrastructure/stress/penultimate_resolver.py` |
| Словник наголосів | `src/infrastructure/stress/ukrainian.py` |
| Службові слова | `src/infrastructure/meter/ukrainian_weak_stress_lexicon.py` |
| HTTP-маппер помилок | `src/infrastructure/http/error_mapper.py` (`DefaultHttpErrorMapper`) |
| Композиція детекції | `src/infrastructure/composition/detection.py` (`DetectionSubContainer`) |
| Композиція валідації | `src/infrastructure/composition/validation.py` (`ValidationSubContainer`) |
| Конфігурація | `src/config.py` |
