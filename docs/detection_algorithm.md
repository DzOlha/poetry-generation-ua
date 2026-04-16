# Алгоритм детекції метру та схеми римування / Detection Algorithm

## Загальний потік / General Flow

```
Текст вірша
    │
    ├─ Розбиття на строфи (_split_stanzas)
    │      по порожніх рядках або по 4 рядки
    │
    ├─ Детекція метру (BruteForceMeterDetector)
    │      перебір 5 метрів × 5 стопностей = 25 комбінацій
    │      для кожної → валідація → accuracy
    │      поріг: >= 0.85
    │
    ├─ Детекція рими (BruteForceRhymeDetector)
    │      перебір ABAB / AABB / ABBA
    │      для кожної → валідація → accuracy
    │      поріг: >= 0.5
    │
    └─ Per-stanza валідація з підсвічуванням
```

---

## 1. Детекція метру / Meter Detection

### 1.1 Brute-force перебір

**Файл:** `src/infrastructure/detection/brute_force_meter_detector.py`

Алгоритм перебирає всі комбінації метру та кількості стоп:

| Метр | Шаблон стопи |
|------|-------------|
| Ямб (iamb) | `u —` |
| Хорей (trochee) | `— u` |
| Дактиль (dactyl) | `— u u` |
| Амфібрахій (amphibrach) | `u — u` |
| Анапест (anapest) | `u u —` |

- Кількість стоп: від 2 до 6
- Для кожної комбінації запускається `PatternMeterValidator.validate()`
- Повертається комбінація з найвищим accuracy >= 0.85

### 1.2 Валідація рядка метру

**Файл:** `src/infrastructure/validators/meter/pattern_validator.py`

Для кожного рядка вірша:

1. **Токенізація:** розбиття на слова, підрахунок складів (кількість голосних)
2. **Очікуваний паттерн:** шаблон стопи × кількість стоп (наприклад, ямб 4-стопний = `u—u—u—u—`)
3. **Фактичний паттерн:** визначення наголосу для кожного слова (див. розділ 3)
4. **Порівняння:** знаходження розбіжностей між фактичним та очікуваним
5. **Толерантність:** деякі розбіжності прощаються (див. розділ 4)
6. **Рішення:** рядок проходить, якщо `кількість_реальних_помилок <= 2` І довжина OK

### 1.3 Толерантність довжини рядка

**Файл:** `src/infrastructure/validators/meter/prosody.py`, метод `line_length_ok`

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

Перебирає три схеми: ABAB, AABB, ABBA.
Поріг accuracy >= 0.5 (при 4 рядках є лише 2 пари, тому accuracy = 0.0 / 0.5 / 1.0).

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
6. Пара вважається римою, якщо score >= 0.7

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

1. **Словник** (`ukrainian-word-stress`): нейронна модель stanza для українських наголосів
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

Модель stanza (~1 ГБ) кешується на рівні модуля (thread-safe singleton),
щоб кілька контейнерів не дублювали її в пам'яті.

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

## 5. Per-stanza логіка в UI / Stanza-level UI Logic

**Файл:** `src/handlers/web/routes/detection.py`

### 5.1 Розбиття на строфи

1. Якщо є порожні рядки між строфами — розбиття по них
2. Якщо порожніх рядків немає — розбиття по 4 рядки
3. Для рими: кількість рядків має бути кратною 4

### 5.2 Три рівні fallback для метру кожної строфи

1. **Full-poem detection** (accuracy >= 0.85)
2. **Per-stanza detection** (accuracy >= 0.85)
3. **Best-guess** (найвищий accuracy > 0, без порога) — для відображення підсвічування

### 5.3 Чекбокси в UI

- Можна обрати "Метр", "Схема римування", або обидва
- Лише метр: приймається будь-яка кількість рядків
- Схема римування: кількість рядків має бути кратною 4

---

## 6. Порогові значення / Thresholds Summary

| Компонент | Поріг | Значення | Файл |
|-----------|-------|----------|------|
| Детекція метру | min accuracy | 0.85 | config.py |
| Детекція рими | min accuracy | 0.5 | config.py |
| Валідація метру (per-line) | allowed mismatches | 2 | config.py |
| Валідація рими (per-pair) | similarity score | 0.7 | phonetic_validator.py |
| Точна рима | score | >= 0.95 | pair_analyzer.py |
| Асонанс/Консонанс | channel score | >= 0.75 | pair_analyzer.py |
| Стопність | feet range | 2-6 | config.py |
| Розмір строфи | stanza size | 4 (фіксований) | config.py |

---

## 7. Ключові файли / Key Files

| Що | Файл |
|----|------|
| Web route (форма → детекція) | `src/handlers/web/routes/detection.py` |
| Сервіс детекції | `src/services/detection_service.py` |
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
| Конфігурація | `src/config.py` |
