# Stress and syllables

> The foundation metre validation stands on. Without accurate stress, metre accuracy collapses — metre is defined by the positions of stressed syllables.

## What this subsystem must deliver

- The **syllable count** of a word.
- The **position of the stressed syllable** in a word (0-based index).

The first is trivial (count vowels). The second is hard: requires either a dictionary or a heuristic.

## Syllables: how they are counted

In Ukrainian a syllable is shaped around a vowel, so `count_syllables(word)` = **the number of vowel letters** in the word.

**Implementation:** [`shared/text_utils_ua.py`](../../src/shared/text_utils_ua.py) — `count_syllables_ua(word)` plus the canonical `VOWELS_UA = "аеєиіїоуюя"` constant. The infrastructure adapter [`UkrainianSyllableCounter`](../../src/infrastructure/stress/syllable_counter.py) wraps that helper behind the `ISyllableCounter` port so callers can be unit-tested with stub counters.

```
"весна"   → 2 (е, а)
"ліс"     → 1 (і)
"україна" → 4 (у, а, ї, а)
"сон"     → 1 (о)
```

Diphthongs like "юа" are counted as two syllables (because "ю" and "а" are separate vowels). This is a deliberate simplification: for Ukrainian it produces accurate results in >99% of cases.

## Stress: why it's hard

Ukrainian stress is **free and mobile**:
- free = may fall on any syllable,
- mobile = the same root in different forms may stress differently (*вікнО → вікОн*).

So rules like "stress is always on the last/penultimate syllable" **do not work** as a single solution. The correct answer: **look it up in a dictionary**.

## Level 1: dictionary lookup

The project uses the open-source [`ukrainian-word-stress`](https://github.com/lang-uk/ukrainian-word-stress) library (lang-uk) + Stanza NLP models. The dictionary holds ~2 M word forms with disambiguation. Roughly 1 GB of unpacked data.

**Wrapper:** [`UkrainianStressDict`](../../src/infrastructure/stress/ukrainian.py) — implements the `IStressDictionary` port. Key method:

```python
def get_stress_index(word: str) -> int | None:
    """Return 0-based vowel index of stressed vowel, or None if unknown."""
```

Details:
- The Stressifier returns the word with a **combining acute accent over the stressed vowel**. The wrapper converts this back into a 0-based vowel index.
- What's returned is a **vowel index**, not a syllable index. For *"украї́на"* (stress on the 3rd vowel) the method returns `2`.
- For **ambiguous** words (*зА́мок* vs *замО́к*) the wrapper defaults to `on_ambiguity="first"` — the first interpretation wins. The strategy is configurable (`first` / `last` / `random`).
- If the `ukrainian-word-stress` library cannot be loaded the constructor logs a warning and `get_stress_index` returns `None`; the upstream `IStressResolver` then falls back to its heuristic.
- The Stressifier instance loads on first call and is **cached in a module-level dict keyed by `on_ambiguity`** — multiple `UkrainianStressDict` instances (e.g. parallel composition containers in tests) share the same backend instead of duplicating the heavy model.

## Level 2: heuristic when the dictionary is silent

[`PenultimateFallbackStressResolver`](../../src/infrastructure/stress/penultimate_resolver.py) implements the `IStressResolver` port, wraps the dictionary, and adds a fallback for out-of-vocabulary words (proper names, rare neologisms, typos).

Algorithm of `resolve(word) -> int`:

1. **Cache.** If `word` was seen, return the cached index from `_cache`.
2. **Dictionary.** Call `stress_dictionary.get_stress_index(word)` (the injected `IStressDictionary`). If non-None, that's the answer.
3. **Fallback `_guess_stress(word)`:**
   - 1 syllable → return `0`.
   - **Suffix rules.** If the word has ≥ 3 syllables and ends in `-ота` → stress on the **last** syllable. The suffix list (`_SUFFIXES_LAST_STRESS`) is extensible.
   - **Final-letter rule:**
     - Word ends in a vowel, `й`, or `ь` (**soft ending**) → stress on the **penultimate** syllable.
     - Word ends in a consonant (**hard ending**) → stress on the **last** syllable.

**Why this heuristic.** Ukrainian phonology has a statistical bias: soft-ending words stress the penultimate syllable in ~79% of cases (Dolatian & Guekguezian, *Cambridge Phonology* 2019). Suffix rules capture the known exceptions. Together this gets ~85–90% accuracy on unseen words — enough for fallback mode.

## Examples

```
"сон"      → 0 (1 syllable → always 0)
"урок"     → 1 (2 syllables; dictionary knows «уро́к»; the heuristic agrees — hard «к» → last)
"книжка"   → 0 (2 syllables; dictionary knows «кни́жка»; the heuristic agrees — soft «а» → penultimate)
"україна"  → 2 (4 syllables; dictionary → «Украї́на»)
"прапор"   → 0 (2 syllables; dictionary knows «пра́пор». Without it the heuristic would return 1 — hard «р» → last)
"пустота"  → 2 (3 syllables; «-ота» suffix rule → last syllable)
"весна"    → 1 (2 syllables; dictionary knows «весна́». Without it the heuristic would return 0 — soft «а» → penultimate — which would be wrong)
```

## Ports (Dependency Inversion)

The stress / syllables / phonetics layer is split into four narrow ports so callers depend on the contract, not the concrete adapter:

| Port | Production adapter | Responsibility |
|------|--------------------|----------------|
| `IStressDictionary` | `UkrainianStressDict` | Vowel-index lookup from the lang-uk Stressifier |
| `ISyllableCounter` | `UkrainianSyllableCounter` | Vowel-counting heuristic |
| `IStressResolver` | `PenultimateFallbackStressResolver` | Composes the two above + heuristic fallback + per-word cache |
| `IPhoneticTranscriber` | `UkrainianIpaTranscriber` | Cyrillic → IPA + `vowel_positions` + `rhyme_part` |

The rhyme pair analyser depends on `IStressResolver`, `ISyllableCounter`, `IPhoneticTranscriber`, and `IStringSimilarity`; the meter validators depend on `IStressResolver` indirectly through `UkrainianProsodyAnalyzer`.

## How this feeds metre validation

The metre validator builds the **actual pattern** of a line like so:

1. Tokenise the line into words.
2. For each word:
   - Count syllables.
   - Resolve stress (via `PenultimateFallbackStressResolver`).
   - Mark the resolved position (within the line) as `—`; everything else is `u`.
3. Exception: **weak-stress words** (conjunctions, prepositions, particles — «і», «та», «на», «не»…) **do not place stress**. They pass as zeroes in the metric grid.

Full details in [`meter_validation.md`](./meter_validation.md).

## Key files

| File | Responsibility |
|------|----------------|
| [`src/shared/text_utils_ua.py`](../../src/shared/text_utils_ua.py) | `VOWELS_UA` constant + `count_syllables_ua` |
| [`src/infrastructure/stress/ukrainian.py`](../../src/infrastructure/stress/ukrainian.py) | `UkrainianStressDict` — Stressifier wrapper + module-level model cache |
| [`src/infrastructure/stress/penultimate_resolver.py`](../../src/infrastructure/stress/penultimate_resolver.py) | `PenultimateFallbackStressResolver` — heuristic + cache |
| [`src/infrastructure/stress/syllable_counter.py`](../../src/infrastructure/stress/syllable_counter.py) | `UkrainianSyllableCounter` adapter for `ISyllableCounter` |
| [`src/infrastructure/phonetics/ukrainian_ipa_transcriber.py`](../../src/infrastructure/phonetics/ukrainian_ipa_transcriber.py) | `UkrainianIpaTranscriber` (`IPhoneticTranscriber` adapter) |
| [`src/infrastructure/meter/ukrainian_weak_stress_lexicon.py`](../../src/infrastructure/meter/ukrainian_weak_stress_lexicon.py) | `UkrainianWeakStressLexicon` — function words that skip stress placement |

## Caveats and limitations

- **Single-process cache:** `UkrainianStressDict` holds the Stressifier instance in a module-level variable. In multi-worker mode (uvicorn with workers > 1) the model is reloaded per process. Fine for prod (start-up cost only) but not ideal.
- **`on_ambiguity="first"`** — loses ~2% of cases where the first interpretation is wrong. Compensated by validator tolerance.
- **Missing dictionary entries for rare forms.** A word like "загорілся" (Russian interference, a malformed Ukrainian) yields `None` from the dictionary → the heuristic treats it as an ordinary word. The result may miss the author's intent.
- **Case.** The dictionary handles both cases; the cache key is as-is.

## See also

- [`meter_validation.md`](./meter_validation.md) — where this subsystem feeds data.
- [`rhyme_validation.md`](./rhyme_validation.md) — uses stress to locate the clausula.
- [`detection_algorithm.md`](./detection_algorithm.md) — uses both for auto-detection.
