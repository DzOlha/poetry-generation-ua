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

A **clausula** is the line ending from the last stressed syllable onward. The classification counts how many **unstressed syllables follow the stressed one** (not the total syllables of the word):

| Type | Unstressed syllables after the stress | Examples |
|------|----------------------------------------|----------|
| Masculine (oxytonic) | 0 | «бі́ль», «сві́т», «ходо́к» (хо-**до́**), «весна́» (вес-**на́**) |
| Feminine (paroxytonic) | 1 | «кни́га» (**кни́**-га), «во́ля» (**во́**-ля), «ро́зум» (**ро́**-зум), «приро́да» (при-**ро́**-да), «молодо́го» (мо-ло-**до́**-го) |
| Dactylic | 2 | «зро́блено» (**зро́**-бле-но), «ма́тери» (**ма́**-те-ри), «найкра́щої» (най-**кра́**-що-ї) |
| Hyperdactylic | 3+ | «приголо́мшуючи» (при-го-**ло́м**-шу-ю-чи) |

> Common pitfall: «ходо́к» is masculine (no unstressed vowel after `о́`), and «ро́зум» / «молодо́го» are feminine (only `у` and `о` respectively follow the stress). What matters is post-stress vowels, not total word length.

A 4-foot iamb (8 syllables) may end on +1 unstressed syllable (feminine clausula, 9 syllables, e.g. line closing on «во́ля») or +2 (dactylic, 10 syllables, e.g. line closing on «зро́блено»). These are **not extra syllables** — they are canonical line endings, described in Kachurovsky and every Ukrainian metrics primer since. Likewise, **catalexis** (a chopped trailing unstressed) is a standard variation: it produces a masculine ending where the strict pattern would have closed on `u`.

That is why `line_length_ok` accepts `+1 u`, `+2 uu`, and `-N u` catalexis, while rejecting everything else (extra stressed syllables = a different foot count = a real error).

### How this compares to alternative approaches

- **Strict character-by-character matching with no tolerance** — theoretically accurate, but in practice ALL classical samples (Shevchenko, Lesia Ukrainka) would fail. Not useful.
- **ML classification of meter from embeddings** — potentially flexible, but opaque and requires a labelled training corpus. This project deliberately refuses that path in favour of **interpretable rules**: every error / tolerance has a name and an explanation.

In short: the system **does not invent its own metric** — it **formalises** rules that already exist in literary tradition into machine-verifiable conditions.

## Definitions

**Metre** is the rhythmic structure of verse: the regular alternation of stressed (`—`) and unstressed (`u`) syllables. The system supports the five canonical Ukrainian metres:

| Metre | Single-foot template | Example |
|-------|---------------------|---------|
| Iamb | `u —` | «Лети́ть весна́» — ле-**ТИ́ТЬ** вес-**НА́** (`u — u —`, 2-foot) |
| Trochee | `— u` | «Зо́рі ся́ють» — **ЗО́**-рі **СЯ́**-ють (`— u — u`, 2-foot) |
| Dactyl | `— u u` | «Ра́дісно сни́лися» — **РА́**-діс-но **СНИ́**-ли-ся (`— u u — u u`, 2-foot) |
| Amphibrach | `u — u` | «Бере́зи зеле́ні» — бе-**РЕ́**-зи зе-**ЛЕ́**-ні (`u — u u — u`, 2-foot) |
| Anapest | `u u —` | «Запалі́ла зоря́» — за-па-**ЛІ́**-ла зо-**РЯ́** (`u u — u u —`, 2-foot) |

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
- **Actual is 1 syllable longer**, last is `u` → OK (**feminine clausula** — line ends on a paroxytone like «во́ля», «кни́га»).
- **Actual is 2 syllables longer**, last two are `uu` → OK (**dactylic clausula** — line ends on «зро́блено», «ма́тери»).
- **Actual is shorter**, dropped positions all `u` and the gap is smaller than one foot → OK (**catalexis** — the unstressed tail of the last foot is cut, producing a masculine close on «бі́ль», «сві́т»). A truncation that drops a `—` position is rejected — that would silently swallow a missing stress.
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

Each line below comes from the test suite — they are real classical lines that the validator accepts. The walk-through shows position-by-position **why**.

### Pyrrhic — Kotlyarevsky's «Еней був парубок моторний» (4-foot iamb, feminine clausula)

```
position:  1   2   3   4   5   6   7   8   9
syllable:  Е   не́й був па́  ру  бок мо  то́р ний
expected:  u   —   u   —   u   —   u   —   u   ← 4-foot iamb + feminine
actual:    u   —   —   —   u   u   u   —   u
```

Two real mismatches:
- **Position 3** «був» — `expected=u`, `actual=—`. «був» is a stressed 1-syllable word; a monosyllable always carries its own stress, so finding it on a weak metric position is **spondee**, tolerated.
- **Position 6** «бок» (last syllable of «па́рубок») — `expected=—`, `actual=u`. The strong position is filled by an unstressed syllable of a polysyllabic content word — that is a **classical pyrrhic**.

The pyrrhic at position 6 is **not** caught by the per-position tolerance (it triggers only for monosyllables and weak words like «та», «в», «і»). It is absorbed by the line-level slack: `allowed_mismatches = 2` lets the line keep up to two real errors.

If the same position 6 had been filled by a function word — e.g. «Еней був добрий, та моторний» with «та» on position 6 — the per-position branch would fire: flag `(monosyllabic=True, weak=True)` ⇒ tolerated outright, no slack consumed.

### Spondee — Lesya Ukrainka's «Ні я хочу крізь сльози сміятись» (3-foot anapest, feminine clausula)

```
position:  1   2   3   4   5    6    7   8   9   10
syllable:  Ні  я   хо́  чу  крізь сльо́ зи  смі я́  тись
expected:  u   u   —   u   u    —    u   u   —   u   ← 3-foot anapest + feminine
actual:    u   u   —   u   —    —    u   u   —   u
```

Mismatch at position 5: «крізь» is a 1-syllable preposition, **but it is not in the weak-stress lexicon** — it is a stressed monosyllable. So `actual=—` while `expected=u`. The flag is `(monosyllabic=True, weak=False)`. The spondee branch fires on the `monosyllabic=True` half — the line passes with **zero** real errors after filtering.

### Catalexis — Sosyura's «Любіть Україну як сонце любіть» (4-foot amphibrach)

```
position:  1   2    3   4   5   6   7   8    9   10  11   (12)
syllable:  Лю  бі́ть У   кра ї́  ну  як  со́н  це  лю  бі́ть   ·
expected:  u   —    u   u   —   u   u   —    u   u   —    u
actual:    u   —    u   u   —   u   u   —    u   u   —    ·
```

The line has **11 syllables** where strict 4-foot amphibrach would give 12. The dropped position (the final `u` of the expected pattern) is unstressed and the gap is one syllable — smaller than the foot size of 3. `line_length_ok` accepts the truncation as **catalexis**, and the line ends on a masculine clausula («любі́ть») instead of the strict `... — u` cadence. If the dropped position had been `—`, the line would have been rejected as a missing stress.

## Key constants

| Constant | Value | Where |
|----------|-------|-------|
| `allowed_mismatches` | `2` | [`BaseMeterValidator.__init__`](../../src/infrastructure/validators/meter/base.py) |
| Allowed length delta | `±2` syllables per rules | [`prosody.py`](../../src/infrastructure/validators/meter/prosody.py) |

## Prosody ports

`UkrainianProsodyAnalyzer` is a single concrete class that satisfies three narrow ports defined in [`src/domain/ports/prosody.py`](../../src/domain/ports/prosody.py):

| Port | Responsibility |
|------|----------------|
| `IStressPatternAnalyzer` | Build the actual realised stress pattern + per-syllable flags from a tokenised line |
| `IExpectedMeterBuilder` | Build the canonical expected stress pattern for `meter × foot_count` |
| `IMismatchTolerance` | Decide which mismatches are tolerated (pyrrhic / spondee / clausula / catalexis) |

`UkrainianProsodyAnalyzer` itself composes three injected collaborators — `IMeterTemplateProvider`, `ISyllableFlagStrategy`, `IStressResolver`, plus an `IWeakStressLexicon` — so any of them can be replaced without touching the analyser.

## Key files

- [`src/infrastructure/validators/meter/pattern_validator.py`](../../src/infrastructure/validators/meter/pattern_validator.py) — pattern validator
- [`src/infrastructure/validators/meter/base.py`](../../src/infrastructure/validators/meter/base.py) — `BaseMeterValidator` template method
- [`src/infrastructure/validators/meter/prosody.py`](../../src/infrastructure/validators/meter/prosody.py) — `UkrainianProsodyAnalyzer` + length tolerance
- [`src/infrastructure/validators/meter/feedback_builder.py`](../../src/infrastructure/validators/meter/feedback_builder.py) — `DefaultLineFeedbackBuilder`
- [`src/domain/ports/prosody.py`](../../src/domain/ports/prosody.py) — narrow prosody ports
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
