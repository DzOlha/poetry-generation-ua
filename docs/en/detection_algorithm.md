# Meter and Rhyme Detection Algorithm

## General Flow

```
Poem text
    |
    +-- HTTP entrypoint: api.routers.detection / web.routes.detection
    |       both inject DetectionService + IMeterValidator + PoetryService
    |       via Depends(get_detection_service / get_meter_validator / get_poetry_service)
    |
    +-- detect_orchestrator.detect_poem(...)
    |       1. Validate request (any aspect selected? non-empty? line count multiple of 4 if rhyme?)
    |       2. DetectionService.detect(poem_text, sample_lines=4) — full-poem pass
    |       3. Split into stanzas (split_stanzas: blank lines, else every 4)
    |       4. Per-stanza meter fallback (full-poem → per-stanza → best-guess)
    |       5. Per-stanza re-validation → annotated `line_displays`
    |
    +-- DetectionService.detect (services.detection_service)
    |       sampler.sample(poem_text, n_lines) → require ≥ default_sample_lines
    |       meter_detector.detect(poem_text)   → BruteForceMeterDetector
    |       rhyme_detector.detect(poem_text)   → BruteForceRhymeDetector
    |       returns DetectionResult(meter: MeterDetection?, rhyme: RhymeDetection?)
```

`DetectionResult.meter` and `.rhyme` are **`None`** when nothing detected; the schemas/templates render that as "not detected" rather than masking with a default.

---

## DetectionService constructor

`DetectionService` no longer takes a `DetectionConfig` object. The current contract is:

```python
class DetectionService(IDetectionService):
    def __init__(
        self,
        sampler: IStanzaSampler,
        meter_detector: IMeterDetector,
        rhyme_detector: IRhymeDetector,
        default_sample_lines: int,   # plain int, not a config struct
        logger: ILogger,
    ) -> None: ...
```

`default_sample_lines` is the floor below which detection is skipped (returns `DetectionResult(meter=None, rhyme=None)` and logs "Poem too short for detection"). The brute-force detectors keep their own `DetectionConfig` reference for thresholds and foot-count range; the service does not.

`FirstLinesStanzaSampler.sample(poem_text, line_count)` simply returns the first `line_count` non-blank lines (joined with `\n`) or `None` when the poem is shorter than that. The constant `4` is the natural default for quatrain detection.

---

## 1. Meter Detection

### 1.1 Brute-force search

**File:** [`src/infrastructure/detection/brute_force_meter_detector.py`](../../src/infrastructure/detection/brute_force_meter_detector.py)

The algorithm iterates over all meter and foot count combinations:

| Meter | Foot template |
|-------|--------------|
| Iamb | `u —` |
| Trochee | `— u` |
| Dactyl | `— u u` |
| Amphibrach | `u — u` |
| Anapest | `u u —` |

- Foot counts: `feet_min` … `feet_max` (defaults `1` … `6` — matched to the generation / validation range so the system can recognise any poem it can itself produce)
- For each combination, the injected `IMeterValidator.validate(text, MeterSpec)` is called — `PatternMeterValidator` by default
- A candidate passes the pre-filter when `accuracy ≥ meter_min_accuracy` (default 0.85)
- **Tie-break:** among the survivors, the candidate with the largest `(accuracy, -total_errors)` tuple wins, where `total_errors = sum(len(line.error_positions))` over the `LineMeterResult`s in the returned `MeterResult`. Semantics: at equal accuracy, the candidate with fewer real-error positions wins. Without this step, ties on accuracy would be resolved by iteration order — and a shorter meter with a permissive length tolerance would silently steal the win from a longer meter that fits exactly (see worked example in §1.3).

### 1.2 Per-line meter validation

**File:** [`src/infrastructure/validators/meter/pattern_validator.py`](../../src/infrastructure/validators/meter/pattern_validator.py)

The detector uses **`PatternMeterValidator`** — the same validator the generation pipeline uses. An empirical run against [`uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) (193 entries) confirmed it is well-calibrated for detection on a modern Ukrainian corpus and does not reject classical lines (Шевченко, Рильський, Антонич) over purely positional deviations.

For each line in the poem:

1. **Tokenization:** split into words, count syllables (number of vowels).
2. **Expected pattern:** foot template × foot count (e.g. iamb 4-foot = `u—u—u—u—`).
3. **Actual pattern:** resolve stress for each word (see section 3).
4. **Comparison:** find mismatches between actual and expected.
5. **Tolerance:** some mismatches are forgiven — pyrrhics, spondees, short-tail catalexis (see section 4).
6. **Decision:** the line passes if `len(real_errors) <= allowed_mismatches` (default 2) AND length is OK.
7. **Export:** `error_positions` is recorded in `LineMeterResult` — its sum across lines is exactly the tie-break signal the detector reads. Tie-breaking by `error_positions` delivers the expected "tighter fit wins" behaviour without sacrificing recall on longer meters.

### 1.3 Worked example: why the tie-break matters

A 2-foot dactyl poem:
```
Крапля скотилася    → [—, u, u, —, u, u]
Голка по шибочках   → [—, u, u, —, u, u]
Тихо відбилася      → [—, u, u, —, u, u]
Казка у кутиках     → [—, u, u, —, u, u]
```

Live detector output:

| Meter (2-foot) | Expected pattern | Errors per line | length_ok | accuracy |
|----------------|-------------------|------------------|-----------|----------|
| **Iamb** | `[u, —, u, —]` (4 syllables) | 2 (right at `allowed_mismatches=2`) | ✓ (via the +2 trailing-unstressed tolerance) | **1.00** |
| **Dactyl** | `[—, u, u, —, u, u]` (6 syllables) | **0** | ✓ (exact length) | **1.00** |

Both meters reach accuracy = 1.00 — iamb only sneaks in via the permissive length tolerance ([`prosody.py:79-80`](../../src/infrastructure/validators/meter/prosody.py#L79-L80)) plus exactly `allowed_mismatches` errors. Without the tie-break, the first iteration-order winner (iamb in [`brute_force_meter_detector.py:17-23`](../../src/infrastructure/detection/brute_force_meter_detector.py#L17-L23)) would carry the day. Tie-break by total `error_positions` (8 for iamb × 4 lines = `total_errors=8` vs dactyl `total_errors=0`) correctly picks dactyl.

### 1.4 Empirical verification

The tie-break logic was introduced after sweeping both strategies — legacy (`accuracy` only) and current (`(accuracy, -total_errors)`) — across the 193-entry [`uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) and comparing against the corpus annotation. At the time the tie-break was introduced:

| Strategy | `meter+feet` matches corpus | No detection |
|----------|------------------------------|--------------|
| legacy | 161/193 (83%) | 19 |
| **current (tie-break)** | **170/193 (88%)** | 19 |

9 net wins, 0 regressions. The remaining 23 mismatches are unchanged — a separate question (stress resolver on longer meters, the 0.85 threshold, 18th-c. syllabotonic inconsistency).

### 1.5 Line-length tolerance

**File:** [`src/infrastructure/validators/meter/prosody.py`](../../src/infrastructure/validators/meter/prosody.py), method `line_length_ok`

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

Tries four schemes in order: **AAAA, ABAB, AABB, ABBA**. AAAA is checked first by design — it is the most restrictive (every pair must rhyme). On a quatrain the looser schemes always pass when AAAA does, so without that ordering monorhyme would be silently reported as ABAB.

Accuracy threshold `rhyme_min_accuracy` (default 0.5). With 4 lines there are only 2 pairs, so accuracy ∈ {0.0, 0.5, 1.0}.

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
6. A pair is considered a rhyme if score >= 0.55

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

1. **Dictionary** (`ukrainian-word-stress`): Stanford NLP's Stanza pipeline (Ukrainian models, ~500 MB) for morphological analysis + stress lookup
2. **Heuristic** (fallback): when the dictionary returns `None`

### 3.2 Stress heuristic

Built on the statistical regularity in Ukrainian phonology where the word-final segment is a strong predictor of default stress placement:

| Word ending | Stress position | Examples |
|-------------|----------------|----------|
| Vowel (a, e, i, o, u, etc.) | Penultimate syllable | stohne, kokhannia, ukraina |
| Soft sign or "y" sound (й, ь) | Penultimate syllable | shyrokyi, zelenyi, misiats |
| Hard consonant (r, n, t, s, ...) | Last syllable | horyth, viter |
| Monosyllabic | Only syllable | lis, Dnipr |

### 3.3 Model singleton

**File:** `src/infrastructure/stress/ukrainian.py`

The Stanza models (~500 MB on first download) are cached at module level
(thread-safe singleton) so that multiple composition containers do not
duplicate them in memory.

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

## 5. Orchestration: per-stanza UI logic

**Files:** `src/handlers/shared/detect_orchestrator.py`, `src/handlers/api/routers/detection.py`, `src/handlers/web/routes/detection.py`

The HTML and JSON API handlers share `detect_orchestrator.detect_poem(...)` so both surfaces produce identical detection facts. Both routes inject their dependencies via FastAPI `Depends`:

```python
service: DetectionService     = Depends(get_detection_service)
poetry: PoetryService         = Depends(get_poetry_service)
meter_validator: IMeterValidator = Depends(get_meter_validator)
```

This replaces the older module-level singletons; tests can override any of them via `app.dependency_overrides`.

### 5.1 Stanza splitting

`split_stanzas(poem_text, stanza_size=4)`:
1. If blank lines exist between stanzas — split on them.
2. If there are no blank separators — fall back to fixed 4-line chunks (only when total line count > 4; otherwise the poem stays as one block).
3. For rhyme detection the orchestrator additionally requires the total line count to be a multiple of 4 — otherwise the request is rejected with a Ukrainian-language error string before any detector runs.

### 5.2 Three-level meter fallback per stanza

1. **Full-poem detection** (`DetectionService.detect`, threshold ≥ `meter_min_accuracy`).
2. **Per-stanza detection** (`DetectionService.detect(stanza_text, sample_lines=STANZA_SIZE)`).
3. **Best-guess** (`_best_guess_meter`: highest accuracy > 0, no threshold) — only for displaying stress highlights.

### 5.3 Per-stanza response shape

Each stanza is re-validated through `PoetryService.validate(...)` to produce annotated character-level stress segments via `handlers.shared.line_displays.line_displays`. Both routes return per-stanza data:

| Field | Meaning |
|-------|---------|
| `meter` | `MeterDetection?` for this stanza |
| `rhyme` | `RhymeDetection?` for this stanza |
| `meter_accuracy` / `rhyme_accuracy` | Accuracy floats from the local validation pass |
| `lines_count` | Number of lines in the stanza |
| `line_displays` | Char-level stress segments — what the SPA / Jinja templates need to highlight stressed syllables |

The API returns `StanzaDetectionSchema` (see `src/handlers/api/schemas.py`); the web handler renders the same data into Jinja templates.

### 5.4 UI checkboxes

- User can select "Meter", "Rhyme scheme", or both.
- Meter only: any number of lines accepted.
- Rhyme scheme: line count must be a multiple of 4.

### 5.5 Error handling

Errors are mapped polymorphically by [`DefaultHttpErrorMapper`](../../src/infrastructure/http/error_mapper.py): each `DomainError` subclass advertises its own `http_status_code` (e.g. `UnsupportedConfigError` → 422, `EmbedderError` → 503, `LLMError` → 502). The mapper just reads `exc.http_status_code` instead of an `isinstance` chain, so adding a new error type does not require editing the mapper.

---

## 6. Thresholds Summary

| Component | Threshold | Value | File |
|-----------|-----------|-------|------|
| Meter detection | min accuracy | 0.85 | config.py |
| Rhyme detection | min accuracy | 0.5 | config.py |
| Meter validation (per-line) | allowed mismatches | 2 | config.py |
| Rhyme validation (per-pair) | similarity score | 0.55 | phonetic_validator.py |
| Exact rhyme | score | >= 0.95 | pair_analyzer.py |
| Assonance / Consonance | channel score | >= 0.75 | pair_analyzer.py |
| Foot count | feet range | 1-6 | config.py |
| Stanza size | stanza size | 4 (fixed) | config.py |

---

## 7. Key Files

| Concern | File |
|---------|------|
| Web route (form → detection) | `src/handlers/web/routes/detection.py` |
| API route (JSON detection) | `src/handlers/api/routers/detection.py` |
| Shared orchestrator | `src/handlers/shared/detect_orchestrator.py` |
| FastAPI dependencies | `src/handlers/api/dependencies.py` (`get_detection_service`, `get_meter_validator`, `get_poetry_service`) |
| Detection service | `src/services/detection_service.py` |
| Stanza sampler | `src/infrastructure/detection/stanza_sampler.py` (`FirstLinesStanzaSampler`) |
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
| HTTP error mapping | `src/infrastructure/http/error_mapper.py` (`DefaultHttpErrorMapper`) |
| Detection composition | `src/infrastructure/composition/detection.py` (`DetectionSubContainer`) |
| Validation composition | `src/infrastructure/composition/validation.py` (`ValidationSubContainer`) |
| Configuration | `src/config.py` |
