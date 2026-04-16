# Meter and Rhyme Detection Algorithm

## General Flow

```
Poem text
    |
    +-- Split into stanzas (_split_stanzas)
    |       by blank lines, or every 4 lines
    |
    +-- Meter detection (BruteForceMeterDetector)
    |       try 5 meters x 5 foot counts = 25 combinations
    |       for each -> validate -> accuracy
    |       threshold: >= 0.85
    |
    +-- Rhyme detection (BruteForceRhymeDetector)
    |       try ABAB / AABB / ABBA
    |       for each -> validate -> accuracy
    |       threshold: >= 0.5
    |
    +-- Per-stanza validation with stress highlighting
```

---

## 1. Meter Detection

### 1.1 Brute-force search

**File:** `src/infrastructure/detection/brute_force_meter_detector.py`

The algorithm iterates over all meter and foot count combinations:

| Meter | Foot template |
|-------|--------------|
| Iamb | `u --` |
| Trochee | `-- u` |
| Dactyl | `-- u u` |
| Amphibrach | `u -- u` |
| Anapest | `u u --` |

- Foot counts: 2 through 6
- For each combination, `PatternMeterValidator.validate()` is called
- The combination with the highest accuracy >= 0.85 is returned

### 1.2 Per-line meter validation

**File:** `src/infrastructure/validators/meter/pattern_validator.py`

For each line in the poem:

1. **Tokenization:** split into words, count syllables (number of vowels)
2. **Expected pattern:** foot template x foot count (e.g., iamb 4-foot = `u--u--u--u--`)
3. **Actual pattern:** resolve stress for each word (see section 3)
4. **Comparison:** find mismatches between actual and expected
5. **Tolerance:** some mismatches are forgiven (see section 4)
6. **Decision:** line passes if `real_error_count <= 2` AND length is OK

### 1.3 Line-length tolerance

**File:** `src/infrastructure/validators/meter/prosody.py`, method `line_length_ok`

| Difference (actual - expected) | Decision | Explanation |
|-------------------------------|----------|-------------|
| 0 | OK | Exact match |
| +1, last = "u" | OK | Feminine clausula |
| +2, last two = "uu" | OK | Dactylic clausula |
| -1..-foot_size, dropped "u" only | OK | Catalexis |
| other | FAIL | |

---

## 2. Rhyme Detection

### 2.1 Brute-force search

**File:** `src/infrastructure/detection/brute_force_rhyme_detector.py`

Tries three schemes: ABAB, AABB, ABBA.
Accuracy threshold >= 0.5 (with 4 lines there are only 2 pairs, so accuracy = 0.0 / 0.5 / 1.0).

### 2.2 Building rhyme pairs

**File:** `src/infrastructure/validators/rhyme/scheme_extractor.py`

The rhyme scheme is treated as a per-stanza template and repeated across all stanzas:

```
Scheme ABAB, 8 lines:
  Stanza 1: pairs (0,2), (1,3)
  Stanza 2: pairs (4,6), (5,7)

Incomplete trailing stanza is ignored.
```

### 2.3 Rhyme pair analysis

**File:** `src/infrastructure/validators/rhyme/pair_analyzer.py`

1. Stress position is resolved for each word
2. From the stressed vowel to end of word = "rhyme part"
3. Words are transcribed to IPA
4. Rhyme parts are suffix-aligned and compared via Levenshtein distance
5. `score = 1 - (edit_distance / max_length)`
6. A pair is considered a rhyme if score >= 0.7

### 2.4 Rhyme precision classification

| Score | Type | Description |
|-------|------|-------------|
| >= 0.95 | EXACT | Perfect rhyme |
| vowels >= 0.75, consonants < 0.75 | ASSONANCE | Vowel-based rhyme |
| consonants >= 0.75, vowels < 0.75 | CONSONANCE | Consonant-based rhyme |
| > 0.0 | INEXACT | Imperfect rhyme |
| 0.0 | NONE | No rhyme |

---

## 3. Stress Resolution

**File:** `src/infrastructure/stress/penultimate_resolver.py`

### 3.1 Resolution hierarchy

1. **Dictionary** (`ukrainian-word-stress`): stanza neural model for Ukrainian stress
2. **Heuristic** (fallback): when the dictionary returns `None`

### 3.2 Stress heuristic

Based on default stress research in free-stress Slavic languages
(Dolatian & Guekguezian, Cambridge Phonology 2019):

| Word ending | Stress position | Examples |
|-------------|----------------|----------|
| Vowel (a, e, i, o, u, etc.) | Penultimate syllable | stohne, kokhannia, ukraina |
| Soft sign or "y" sound (й, ь) | Penultimate syllable | shyrokyi, zelenyi, misiats |
| Hard consonant (r, n, t, s, ...) | Last syllable | horyth, viter |
| Monosyllabic | Only syllable | lis, Dnipr |

Accuracy on test sample: ~79%.

### 3.3 Model singleton

**File:** `src/infrastructure/stress/ukrainian.py`

The stanza model (~1 GB) is cached at module level (thread-safe singleton)
so that multiple composition containers do not duplicate it in memory.

---

## 4. Weak Stress Words (Function Words)

**File:** `src/infrastructure/meter/ukrainian_weak_stress_lexicon.py`

### 4.1 Effect on stress pattern

Monosyllabic function words ("i", "do", "yak", "bo", "ta", "ne"...)
**receive no stress** in the actual pattern -- they remain marked as "u" (unstressed).

Polysyllabic function words ("tvoi", "vona", "yakshcho"...)
receive normal stress, but mismatches with the expected pattern are **tolerated**.

### 4.2 Tolerance rules

**File:** `src/infrastructure/validators/meter/prosody.py`, method `is_tolerated_mismatch`

A mismatch at a given position is forgiven if:
- The word at that position is **monosyllabic** (spondee/pyrrhic for content words), OR
- The word at that position is a **function word** (weak stress word)

---

## 5. Stanza-level UI Logic

**File:** `src/handlers/web/routes/detection.py`

### 5.1 Stanza splitting

1. If blank lines exist between stanzas -- split on them
2. If no blank lines -- split every 4 lines
3. For rhyme detection: total line count must be a multiple of 4

### 5.2 Three-level meter fallback per stanza

1. **Full-poem detection** (accuracy >= 0.85)
2. **Per-stanza detection** (accuracy >= 0.85)
3. **Best-guess** (highest accuracy > 0, no threshold) -- for displaying stress highlights

### 5.3 UI checkboxes

- User can select "Meter", "Rhyme scheme", or both
- Meter only: any number of lines accepted
- Rhyme scheme: line count must be a multiple of 4

---

## 6. Thresholds Summary

| Component | Threshold | Value | File |
|-----------|-----------|-------|------|
| Meter detection | min accuracy | 0.85 | config.py |
| Rhyme detection | min accuracy | 0.5 | config.py |
| Meter validation (per-line) | allowed mismatches | 2 | config.py |
| Rhyme validation (per-pair) | similarity score | 0.7 | phonetic_validator.py |
| Exact rhyme | score | >= 0.95 | pair_analyzer.py |
| Assonance / Consonance | channel score | >= 0.75 | pair_analyzer.py |
| Foot count | feet range | 2-6 | config.py |
| Stanza size | stanza size | 4 (fixed) | config.py |

---

## 7. Key Files

| Concern | File |
|---------|------|
| Web route (form -> detection) | `src/handlers/web/routes/detection.py` |
| Detection service | `src/services/detection_service.py` |
| Meter detector (brute-force) | `src/infrastructure/detection/brute_force_meter_detector.py` |
| Rhyme detector (brute-force) | `src/infrastructure/detection/brute_force_rhyme_detector.py` |
| Meter validator | `src/infrastructure/validators/meter/pattern_validator.py` |
| Prosody analyzer | `src/infrastructure/validators/meter/prosody.py` |
| Rhyme validator | `src/infrastructure/validators/rhyme/phonetic_validator.py` |
| Rhyme scheme extractor | `src/infrastructure/validators/rhyme/scheme_extractor.py` |
| Rhyme pair analyzer | `src/infrastructure/validators/rhyme/pair_analyzer.py` |
| Stress resolver | `src/infrastructure/stress/penultimate_resolver.py` |
| Stress dictionary | `src/infrastructure/stress/ukrainian.py` |
| Weak stress lexicon | `src/infrastructure/meter/ukrainian_weak_stress_lexicon.py` |
| Configuration | `src/config.py` |
