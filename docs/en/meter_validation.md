# Metre validation

> The algorithm that checks whether a line follows the requested rhythmic pattern — with realistic tolerance for standard prosodic variations.

## Linguistic foundations of the rules

Every rule in this subsystem traces to an established convention of Ukrainian versification. This section is a short field guide: **which rules, why exactly these, what they rest on**.

### Why these 5 canonical meters

Iamb, trochee, dactyl, amphibrach, anapest — the standard set of **syllabotonic** meters in classical Ukrainian poetry from Kotlyarevsky and Shevchenko onward. Codified in:

- **I. Kachurovsky** (1967) "Strophica" / "Metrics".
- **M. Sydorenko** (1985) "Ukrainian Versification".
- **M. Tkachenko** (1996) "The Art of the Word".

Syllabotonic meter rests on **regular alternation of stressed and unstressed syllables** — that *is* the definition of meter. Everything else (blank verse, free verse, 18th-century syllabic verse) is outside this system: those forms have no deterministic template that can be machine-verified.

### Why the soft error budget (`allowed_mismatches=2`)

Classical Ukrainian poetry **does not require 100% conformance**: the canon admits **prosodic substitutions** — pyrrhic (an unstressed syllable on a strong position) and spondee (a stressed syllable on a weak one). This is fixed-curriculum verse-theory material in Ukrainian philology. A budget of 2 errors per line lets canonical samples pass without false-failure.

### Why the weak-stress lexicon contains exactly these words

In Ukrainian phonology, **function words** (conjunctions, prepositions, particles, personal pronouns) usually do not carry their own word-level stress in spoken language — they cliticise onto the adjacent content word. Documented in:

- **Yu. Karpenko** (1996) "Phonetics of Ukrainian".
- **N. Totska** (1981) "Modern Ukrainian Literary Language: Phonetics".

So when «і», «та», «з», «не» fall on a "strong" metric position, that is not an authorial error — it is normal language behaviour. The list is in [`UkrainianWeakStressLexicon`](../../src/infrastructure/meter/ukrainian_weak_stress_lexicon.py).

### Why monosyllables are also tolerated

In addition to the lexicon, **any monosyllabic word** on a "weak" position is tolerated — because a monosyllable objectively has only one syllable and that syllable necessarily carries stress; if it lands on a "weak" position, that is poetic licence (a spondee), not a mistake.

### Why feminine / dactylic clausulae and catalexis are allowed

A **clausula** is the line ending from the last stressed syllable onward. Canonical typology:

| Type | Unstressed syllables after the stress | Example |
|------|----------------------------------------|---------|
| Masculine (oxytonic) | 0 | «бі́ль», «сві́т» |
| Feminine (paroxytonic) | 1 | «кни́га», «ходо́к» |
| Dactylic | 2 | «ро́зум», «молодо́го» |
| Hyperdactylic | 3+ | «розумі́ється» |

A 4-foot iamb (8 syllables) may end on +1 unstressed syllable (feminine clausula, 9 syllables) or +2 (dactylic, 10 syllables). These are **not extra syllables** — they are canonical line endings, described in Kachurovsky and every Ukrainian metrics primer since. Likewise, **catalexis** (a chopped trailing unstressed) is a standard variation.

That is why `line_length_ok` accepts `+1 u`, `+2 uu`, and `-N u` catalexis, while rejecting everything else (extra stressed syllables = a different foot count = a real error).

### How this compares to alternative approaches

- **Strict character-by-character matching with no tolerance** — theoretically accurate, but in practice ALL classical samples (Shevchenko, Lesia Ukrainka) would fail. Not useful.
- **ML classification of meter from embeddings** — potentially flexible, but opaque and requires a labelled training corpus. This project deliberately refuses that path in favour of **interpretable rules**: every error / tolerance has a name and an explanation.

In short: the system **does not invent its own metric** — it **formalises** rules that already exist in literary tradition into machine-verifiable conditions.

## Definitions

**Metre** is the rhythmic structure of verse: the regular alternation of stressed (`—`) and unstressed (`u`) syllables. The system supports the five canonical Ukrainian metres:

| Metre | Single-foot template | Example |
|-------|---------------------|---------|
| Iamb | `u —` | Vit*ER* po*VIV* |
| Trochee | `— u` | *SA*dok *VYSH*nevyi |
| Dactyl | `— u u` | *PA*da lys*TOK* ty*KHEN*ko |
| Amphibrach | `u — u` | za*SYA*yaly *ZO*ry |
| Anapest | `u u —` | yak na *MYT*' zaby*LOS'* sertse |

Line length is measured in **feet** — how many times the template repeats in a row. 4-foot iamb = `u — u — u — u —` (8 syllables).

## Algorithm

The single `IMeterValidator` implementation is `PatternMeterValidator`: build the expected pattern, build the actual pattern, compare position-by-position with tolerance for pyrrhic / spondee / catalexis. Wired through DI as `meter_validator()` in [`composition/validation.py`](../../src/infrastructure/composition/validation.py); used by **both generation** and **detection** ([`composition/detection.py`](../../src/infrastructure/composition/detection.py)) — by generation because the feedback loop needs precise error positions, by detection because an empirical run against [`uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) showed this validator is best calibrated for the natural variability of the classical corpus. The detection tie-break is built on `error_positions` (the field Pattern emits) — see [`detection_algorithm.md §1.1`](./detection_algorithm.md#11-brute-force-search).

## How PatternMeterValidator works

### 1. Build the expected pattern

[`UkrainianMeterTemplateProvider.template_for(name)`](../../src/infrastructure/meter/ukrainian_meter_templates.py) returns the base foot by name:

```python
"ямб"       → ["u", "—"]
"хорей"     → ["—", "u"]
"дактиль"   → ["—", "u", "u"]
"амфібрахій" → ["u", "—", "u"]
"анапест"   → ["u", "u", "—"]
```

Multiply by `foot_count`:

```
4-foot iamb    → ["u", "—"] * 4 = ["u","—","u","—","u","—","u","—"]
3-foot dactyl  → ["—", "u", "u"] * 3 = ["—","u","u","—","u","u","—","u","u"]
```

### 2. Build the actual pattern

[`UkrainianProsodyAnalyzer.actual_stress_pattern(words, syllables_per_word)`](../../src/infrastructure/validators/meter/prosody.py) builds the pattern for a concrete line:

1. **Tokenise** into words via `ITextProcessor` (yields words + per-word syllable counts).
2. Initialise pattern as `["u"] * total_syllables`.
3. For each word:
   - **If the word is monosyllabic AND in the weak-stress lexicon** — skip (no stress placed). Weak words: conjunctions (і, та, й), prepositions (на, в, у, з, до), particles (не, ні), personal pronouns (я, ти, він) — see [`UkrainianWeakStressLexicon`](../../src/infrastructure/meter/ukrainian_weak_stress_lexicon.py).
   - Otherwise — resolve the stressed vowel index via `IStressResolver` (see [`stress_and_syllables.md`](./stress_and_syllables.md)) and mark that position (within the line) as `—`.

In parallel, [`DefaultSyllableFlagStrategy`](../../src/infrastructure/meter/syllable_flag_strategy.py) attaches per-syllable `(is_monosyllabic, is_weak)` flags so the tolerance step can ignore mismatches at those positions.

### 3. Compare with tolerance

Algorithm of [`PatternMeterValidator._validate_line(line, meter)`](../../src/infrastructure/validators/meter/pattern_validator.py):

1. **Raw mismatches** — positions where `actual[i] != expected[i]`.
2. **Filtering:** each raw mismatch passes through `is_tolerated_mismatch(pos, actual, expected, flags)`. A mismatch is TOLERATED when at that position sits a **monosyllable** (e.g. «і», «вже») OR a word from the **weak-stress lexicon**. Both cover the classical *pyrrhic* (unstressed at strong position) and *spondee* (stressed at weak position) substitutions.
3. **Error threshold:** `allowed_mismatches = 2` by default. If post-filter errors ≤ 2 AND `line_length_ok(...)` holds → the line is valid.

### 4. Length tolerance

[`UkrainianProsodyAnalyzer.line_length_ok(actual, expected)`](../../src/infrastructure/validators/meter/prosody.py) compares the lengths of expected vs actual patterns:

- **Exact match** → OK.
- **Actual is 1 syllable longer**, last is `u` → OK (**feminine clausula**).
- **Actual is 2 syllables longer**, last two are `uu` → OK (**dactylic clausula**).
- **Actual is shorter**, dropped positions all `u` and the gap is smaller than one foot → OK (**catalexis**). A truncation that drops a `—` position is rejected — that would silently swallow a missing stress.
- **Anything else** → not OK.

This captures the classical prosodic deviations recognised by literary tradition as acceptable.

### 5. Per-poem aggregation (template method)

[`BaseMeterValidator.validate(poem, meter_spec)`](../../src/infrastructure/validators/meter/base.py) is a template method that owns the per-poem aggregation. Subclasses implement `_validate_line(line, meter)` only.

1. Split the poem into lines via the injected `ITextProcessor`.
2. For each line call `_validate_line(...)` → `LineMeterResult`.
3. Aggregate:
   - `ok = all(line.ok for line in lines)` — the poem is valid iff every line is valid.
   - `accuracy = valid_lines / total_lines` — fraction of valid lines.
   - For each failing line, the injected [`DefaultLineFeedbackBuilder`](../../src/infrastructure/validators/meter/feedback_builder.py) maps `LineMeterResult` → a structured [`LineFeedback`](../../src/domain/models/feedback.py) DTO (lives in `src.domain.models.feedback`). The feedback formatter renders these into the natural-language strings the LLM sees.

## Tolerated cases with examples

### Pyrrhic

«Садок вишневий коло хати.» — 4-foot iamb:
- Expected: `u — u — u — u —` (8 syllables)
- Actual:   `u — u — u u u —` (positions 5-6 = «коло» — weak-stress word, skipped).

Pyrrhic = an expected-stress position covered by an unstressed weak word. Tolerated → line OK.

### Spondee

«Стій! Час йти!» — 2-foot iamb:
- Expected: `u — u —`
- Actual:   `— — — —` (all words — stressed monosyllables)

Raw divergence at every position. But every mismatching word is a monosyllable → `is_tolerated_mismatch` returns True → after filtering 0 errors → line OK.

### Catalexis

«Летять літа.» — 2-foot iamb (4 expected syllables):
- Expected: `u — u —`
- Actual:   `u — u`    (3 syllables)

Delta -1, the dropped position is unstressed in the expected pattern. `line_length_ok` permits this — "dropped an unstressed closing position — that's catalexis." Tolerated → OK. (If the dropped position had been `—`, the line would be rejected as a missing-stress error.)

Exact semantics for `—`/`u` at the dropped position — see [`prosody.py`](../../src/infrastructure/validators/meter/prosody.py).

## Key constants

| Constant | Value | Where |
|----------|-------|-------|
| `allowed_mismatches` | `2` | [`BaseMeterValidator.__init__`](../../src/infrastructure/validators/meter/base.py) |
| Allowed length delta | `±2` syllables per rules | [`prosody.py`](../../src/infrastructure/validators/meter/prosody.py) |

## Prosody ports (Interface Segregation)

`UkrainianProsodyAnalyzer` is a single concrete class but it satisfies four narrow ports defined in [`src/domain/ports/prosody.py`](../../src/domain/ports/prosody.py):

| Port | Responsibility |
|------|----------------|
| `IStressPatternAnalyzer` | Build the actual realised stress pattern + per-syllable flags from a tokenised line |
| `IExpectedMeterBuilder` | Build the canonical expected stress pattern for `meter × foot_count` |
| `IMismatchTolerance` | Decide which mismatches are tolerated (pyrrhic / spondee / clausula / catalexis) |
| `IProsodyAnalyzer` | Facade union of the three above — **deprecated for new code** |

The audit flagged `IProsodyAnalyzer` as an Interface Segregation smell: most callers only need one of the sub-ports, but depending on the union forces them to know about (and mock) the whole surface. `PatternMeterValidator` and `DefaultLineFeedbackBuilder` continue to depend on the union for backward compatibility, but **new code must depend on the narrowest port that satisfies its actual contract**. The deprecation note lives in the docstring of `IProsodyAnalyzer`.

`UkrainianProsodyAnalyzer` itself composes three injected collaborators — `IMeterTemplateProvider`, `ISyllableFlagStrategy`, `IStressResolver`, plus an `IWeakStressLexicon` — so any of them can be replaced without touching the analyser.

## Key files

- [`src/infrastructure/validators/meter/pattern_validator.py`](../../src/infrastructure/validators/meter/pattern_validator.py) — pattern validator
- [`src/infrastructure/validators/meter/base.py`](../../src/infrastructure/validators/meter/base.py) — `BaseMeterValidator` template method
- [`src/infrastructure/validators/meter/prosody.py`](../../src/infrastructure/validators/meter/prosody.py) — `UkrainianProsodyAnalyzer` + length tolerance
- [`src/infrastructure/validators/meter/feedback_builder.py`](../../src/infrastructure/validators/meter/feedback_builder.py) — `DefaultLineFeedbackBuilder`
- [`src/domain/ports/prosody.py`](../../src/domain/ports/prosody.py) — narrow prosody ports + deprecated facade
- [`src/domain/models/feedback.py`](../../src/domain/models/feedback.py) — `LineFeedback` DTO (note: moved from `src/domain/feedback.py`)
- [`src/infrastructure/meter/ukrainian_meter_templates.py`](../../src/infrastructure/meter/ukrainian_meter_templates.py) — `UkrainianMeterTemplateProvider` (5 canonical meters)
- [`src/infrastructure/meter/syllable_flag_strategy.py`](../../src/infrastructure/meter/syllable_flag_strategy.py) — `DefaultSyllableFlagStrategy`
- [`src/infrastructure/meter/ukrainian_weak_stress_lexicon.py`](../../src/infrastructure/meter/ukrainian_weak_stress_lexicon.py) — weak-stress lexicon
- [`src/infrastructure/composition/validation.py`](../../src/infrastructure/composition/validation.py) — DI wiring of validators and feedback formatter

## Caveats and limitations

- **Weak-stress lexicon is a closed list.** Words not included may be wrongly treated as fully stressed. Add new entries sceptically — this affects every line's validation.
- **No phonetic-based tolerance.** When the model stresses a rare word the Stressifier doesn't know, `PenultimateFallbackStressResolver` gives a heuristic that may diverge from the author's intent.
- **2 errors per line** is an experimentally chosen threshold. Stricter — the model fails even technically correct lines due to resolver noise. Looser — obvious failures slip through.

## See also

- [`stress_and_syllables.md`](./stress_and_syllables.md) — where stress data comes from.
- [`rhyme_validation.md`](./rhyme_validation.md) — the parallel rhyme-check algorithm.
- [`feedback_loop.md`](./feedback_loop.md) — how metre violations feed regeneration.
- [`detection_algorithm.md`](./detection_algorithm.md) — the reverse problem: auto-detect metre.
