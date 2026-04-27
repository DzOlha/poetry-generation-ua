# Rhyme validation

> The algorithm that compares line endings **by sound**, not by spelling. Critical nuance: rhyme is phonetics, so first we transcribe to IPA, then compute a mathematical distance between the sounds.

## Linguistic foundations of the rules

The rhyme rules in this system are **not invented from scratch** — they formalise the canonical definition of rhyme in Ukrainian poetics. In short: **rhyme = phonetic similarity from the stressed vowel to the end of the word**, with a typology (exact / assonance / consonance / inexact).

### The canonical definition

"Rhyme is the sound recurrence in the line endings of two (or more) verses, beginning with the stressed vowel and covering all subsequent sounds" — the standard formulation in:

- **I. Kachurovsky** (1967) "Phonics" / "Strophica".
- **M. Sydorenko** (1985) "Ukrainian Versification".
- **N. Kostenko** (2006) "Ukrainian Versification of the 20th century".

Key phrases — **"sound recurrence", "stressed vowel", "all subsequent sounds"**. Every rule below derives from them:

| Rule in the system | What it reflects in the canon |
|---------------------|--------------------------------|
| IPA transcription | "sound recurrence" — compare phonetics, not orthography |
| Rhyme part starts at the stressed vowel | "begins with the stressed vowel" |
| Left-aligned, full-length comparison | "covers all subsequent sounds" — no trimming |
| EXACT / ASSONANCE / CONSONANCE / INEXACT classification | the standard rhyme typology in Kachurovsky |
| Stressed-vowel gate | no stressed-vowel match → not a rhyme (exception: consonance) |

### Why exactly these four types

Canonical typology of modern Ukrainian poetics:

- **Exact (EXACT)** — full sound match from the stressed vowel onward («біль / ціль»).
- **Assonance** — vowels match, consonants differ («дивиться / висіти»).
- **Consonance / dissonance** — consonants match, vowels differ («гра́д / звід», «по́лем / до́лом»).
- **Inexact** — there is some overlap but neither the vowels nor the consonants reach the 75% threshold.

This taxonomy is present in classics from Kachurovsky to modern textbooks. The implementation in [`_classify_precision`](../../src/infrastructure/validators/rhyme/pair_analyzer.py) is a direct realisation: it computes vowel-channel and consonant-channel similarity separately and classifies by the 0.75 threshold.

### Why consonance matters more than strict equivalence

Textbooks state plainly: **modern Ukrainian poetry actively uses inexact rhymes** (assonance, consonance), and this is not a defect but an expressive device (Shevchenko, Kostenko, Antonych). So the validator does not require 100% sound match — it accepts a pair as a rhyme when `score ≥ 0.55` AND classification ≠ NONE.

### What is intentionally out of scope

The canon also names **deep rhymes, supporting rhymes, banal rhymes** — classifying these requires contextual analysis of the whole poem, beyond what this algorithm does. We only check whether a pair rhymes **at all**, not its artistic value.

## Why phonetics, not letter-level comparison

Classic examples:
- "**біль**" / "**ціль**" — different letters, identical sounds `[b⁽ʲ⁾ilʲ]` / `[tsʲilʲ]` — a **real** rhyme.
- "**вода**" / "**сода**" — looks similar, sounds `[voˈda]` / `[ˈsɔda]` — stress in different positions, **not** a real rhyme (weak at best).
- "**спить**" / "**спить**" — identical spelling and sound — **tautological** rhyme (actually not a rhyme at all, just a repeated word).

Conclusion: spelling → misleading. We need phonetic transcription. In Ukrainian this is mostly a clean translation of Cyrillic to IPA (International Phonetic Alphabet) by simple rules.

## High-level flow

```
Poem              →  Scheme "ABAB"  →  line pairs [(0,2), (1,3)]
   │
   └─ for each pair:
        │
        ├─ take the last word of both lines
        ├─ resolve stress in both
        ├─ extract the rhyme part (from stressed vowel to line end, IPA-transcribed)
        ├─ stressed-vowel gate: differing stressed vowels are accepted only
        │   when the stressed-syllable consonants match (consonance pattern)
        ├─ Levenshtein on phonemes (left-aligned from the stressed vowel, no trimming)
        ├─ classify clausula (MASCULINE / FEMININE / DACTYLIC / HYPERDACTYLIC)
        ├─ classify rhyme precision (EXACT / ASSONANCE / CONSONANCE / INEXACT / NONE)
        └─ decide is_valid (similarity ≥ threshold)
```

The phonetic chain is encapsulated in [`PhoneticRhymePairAnalyzer`](../../src/infrastructure/validators/rhyme/pair_analyzer.py) (an `IRhymePairAnalyzer` implementation). It returns a `RhymePairAnalysis` value object with all the diagnostic fields (`rhyme_part_a/b`, `score`, `clausula_a/b`, `precision`). [`PhoneticRhymeValidator`](../../src/infrastructure/validators/rhyme/phonetic_validator.py) orchestrates: it takes line splitting, tokenisation, scheme extraction, the pair analyser, and a threshold — and produces a `RhymeResult` with structured `PairFeedback` for every failing pair.

## 1. Extracting pairs from the scheme

[`StandardRhymeSchemeExtractor`](../../src/infrastructure/validators/rhyme/scheme_extractor.py) takes a scheme string and a stanza line count. Returns `list[tuple[int, int]]` — 0-based line index pairs that must rhyme.

Supported schemes (4 lines per stanza):

| Scheme | Pairs in a stanza | Meaning |
|--------|-------------------|---------|
| ABAB | (0, 2), (1, 3) | Alternate rhyme |
| AABB | (0, 1), (2, 3) | Coupled (paired) |
| ABBA | (0, 3), (1, 2) | Enclosed |
| AAAA | (0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3) | Monorhyme — all pairs |

For multi-stanza poems the pattern repeats with an offset: an 8-line ABAB poem yields `[(0,2), (1,3), (4,6), (5,7)]`.

Parser algorithm:
1. Split the scheme into letters (*A, B, A, B*).
2. Group line indices by letter: *{A: [0, 2], B: [1, 3]}*.
3. Generate all **pair combinations** within each group (not permutations — (0,2) == (2,0)).
4. Sort → repeat across stanzas.
5. Empty scheme or fully unique letters (like "ABCD") → `UnsupportedConfigError` in Ukrainian.

## 2. The clausula — what we actually compare

**Clausula** is the line suffix from the **stressed syllable of the last word to the line's end**. Everything before the stressed syllable is not part of the rhyme.

For the line *«Де тихо світяться вогні́»*:
- Last word: "вогні́", stress on "і́" (position 1 since 2 syllables: во-гні).
- Clausula: `гні́` (1 syllable — **masculine**).

For *«Ворушаться тіні чужо́го»*:
- Last word: "чужо́го", stress on "о́" in "-жо-" (position 1 of 3).
- Clausula: `жо́го` (2 syllables — **feminine**).

Clausula classification (the [`ClausulaType`](../../src/domain/value_objects.py) enum) by unstressed count after stress:

| Enum value | Unstressed after | Examples |
|------------|------------------|----------|
| `MASCULINE` (чоловіча) | 0 | біль, світ |
| `FEMININE` (жіноча) | 1 | ходок, книга |
| `DACTYLIC` (дактилічна) | 2 | розум, молодого |
| `HYPERDACTYLIC` (гіпердактилічна) | 3+ | розумі́ється |
| `UNKNOWN` | — | empty / unstressable input |

Implementation: [`PhoneticRhymePairAnalyzer._detect_clausula(word)`](../../src/infrastructure/validators/rhyme/pair_analyzer.py) — counts syllables via the injected `ISyllableCounter` and uses `IStressResolver` to locate the stressed syllable. The rhyme part itself is built by [`UkrainianIpaTranscriber.rhyme_part(word, stress_idx)`](../../src/infrastructure/phonetics/ukrainian_ipa_transcriber.py).

## 3. IPA transcription

[`UkrainianIpaTranscriber`](../../src/infrastructure/phonetics/ukrainian_ipa_transcriber.py) converts a Cyrillic string to IPA. Simplified map:

```
а → a    о → ɔ   я → ʲa / ja   '  → ʲ (palatalisation)
е → ɛ    у → u   ю → ʲu / ju   ь  → ʲ (palatalisation)
и → ɪ    і → i   є → ʲɛ / jɛ   ґ  → ɡ
unstressed е → ɛ or ɘ  (simplified to ɛ)
...
```

Important rules:
- **Iotation.** `я`, `ю`, `є`, `ї` after a vowel or at the start of a word produce **two sounds**: `ja`, `ju`, `jɛ`, `ji`. After a consonant — `ʲa`, `ʲu`, `ʲɛ`, `i` (with preceding palatalisation).
- **Soft sign `ь`** transcribes as palatalisation of the preceding consonant `[ʲ]`, not a separate phone.
- **Voiced/voiceless consonants** — final-devoicing does NOT apply in Ukrainian (unlike Russian). So "сад" = `[sad]`, not `[sat]`.

Examples:
```
"сон"    → "sɔn"
"вогні"  → "vɔɡnʲi"
"тіні"   → "tʲini"
"мрія"   → "mrʲija" (modern norm — with j)
"країни" → "krajinɪ"
```

## 4. Stressed-vowel gate

[`PhoneticRhymePairAnalyzer._stressed_syllables_align(r_a, r_b)`](../../src/infrastructure/validators/rhyme/pair_analyzer.py):

The canonical Ukrainian rhyme rule is **identity of the stressed (anchor) vowel** plus similarity of the sounds that follow. Before computing Levenshtein we check whether the pair is even admissible:

| Case | Action |
|------|--------|
| Stressed vowels **match** | Pair proceeds to scoring (exact / assonance / inexact rhyme) |
| Stressed vowels **differ**, but stressed-syllable consonants have similarity ≥ 0.75 | Pair proceeds (this is the **consonance** pattern: «по́лем / до́лом», «гра́д / звід») |
| Stressed vowels **differ** and stressed-syllable consonants differ too | Pair is rejected (`score = 0`, `precision = NONE`) — the words share only an unstressed grammatical suffix (e.g. «шибочка́х / кутика́х» share «-ках» but the stressed syllables are unrelated) |

«Stressed-syllable consonants» = IPA consonants between the stressed vowel and the next vowel; for masculine clausulas — the entire post-stress coda.

## 5. Normalised Levenshtein similarity

[`PhoneticRhymePairAnalyzer._suffix_aligned_score(r_a, r_b)`](../../src/infrastructure/validators/rhyme/pair_analyzer.py):

1. **Left-aligned comparison.** Both IPA rhyme parts already start at the stressed vowel, so they are compared from the start with no trimming. A length disparity (e.g. an 8-character rhyme part for «ши́бочках» versus 4 characters for «ку́тиках») naturally lowers the score — this is the canonical requirement that the post-stress sequences must coincide.
2. **Levenshtein** — minimum insertions / deletions / substitutions to convert one string to another (via the injected `IStringSimilarity` port).
3. **Normalisation:** `similarity = 1 - (distance / max(len_a, len_b))`.
4. Returns a value in `[0, 1]` where 1 = identical.

The analyser additionally tries the **resolved stress position** *and* the **penultimate position** (when they differ) and picks the candidate pair that survives the gate with the highest score — a guard against noisy stress resolution on unfamiliar words.

The Levenshtein implementation lives in [`src/shared/string_distance.py`](../../src/shared/string_distance.py), wrapped behind the `IStringSimilarity` port.

## 6. Rhyme classification

The [`RhymePrecision`](../../src/domain/value_objects.py) enum tags each pair. [`PhoneticRhymePairAnalyzer._classify_precision(rhyme_a, rhyme_b, overall_score)`](../../src/infrastructure/validators/rhyme/pair_analyzer.py):

```
overall_score ≥ 0.95  → EXACT       (exact rhyme: "біль" / "ціль")

else:
  trim both rhyme parts to the shorter length (suffix alignment)
  vowels_X      = [c for c in trimmed_X if c in "aeiouɪ"]
  consonants_X  = [c for c in trimmed_X if c not in vowels]

  vow_sim = similarity(vowels_a, vowels_b)
  con_sim = similarity(consonants_a, consonants_b)

  vow_sim ≥ 0.75 AND con_sim < 0.75   → ASSONANCE
  con_sim ≥ 0.75 AND vow_sim < 0.75   → CONSONANCE
  overall_score > 0                    → INEXACT
  overall_score == 0                   → NONE
```

Interpretation:
- **EXACT** (точна) — full sound match from the stressed vowel onward ("біль / ціль", "день / пень").
- **ASSONANCE** (асонансна) — vowels match, consonants differ ("дивиться" / "висіти").
- **CONSONANCE** (консонансна) — consonants match, vowels differ ("полем" / "долом").
- **INEXACT** (неточна) — partial match, neither pure assonance nor consonance.
- **NONE** — no meaningful similarity.

Every type except NONE **counts as rhyming** if `score ≥ 0.55` (validity threshold). The classified type is stored in `RhymePairAnalysis.precision` and propagated to `PairFeedback.precision` for UI display and LLM feedback.

## 7. Per-poem aggregation

[`PhoneticRhymeValidator.validate(poem_text, rhyme_scheme)`](../../src/infrastructure/validators/rhyme/phonetic_validator.py):

1. Split the poem into lines via `ILineSplitter`.
2. Extract pairs via `IRhymeSchemeExtractor` ([`StandardRhymeSchemeExtractor`](../../src/infrastructure/validators/rhyme/scheme_extractor.py)).
3. For each pair call `IRhymePairAnalyzer.analyze(...)` → `RhymePairAnalysis`, then wrap into `RhymePairResult(ok=score ≥ threshold, ...)`.
4. Aggregate:
   - `ok = all(pair.ok for pair in pair_results)`.
   - `accuracy = valid_pairs / total_pairs` (or `1.0` if there are no pairs).
   - Collect a [`PairFeedback`](../../src/domain/models/feedback.py) (note: structured DTO now lives in `src.domain.models.feedback`, moved from `src.domain.feedback`) per invalid pair. `IFeedbackFormatter` renders the DTO into the natural-language string the LLM sees.

## Thresholds and constants

| Constant | Value | Where |
|----------|-------|-------|
| `EXACT_THRESHOLD` | `0.95` | [`pair_analyzer.py`](../../src/infrastructure/validators/rhyme/pair_analyzer.py) |
| `ASSONANCE_CONSONANCE_THRESHOLD` | `0.75` | same file |
| `rhyme_threshold` (pair validity) | `0.55` | `ValidationConfig` → `PhoneticRhymeValidator` |
| IPA vowels | `{a, e, i, o, u, ɪ, ɛ, ɔ}` | `_IPA_VOWELS` in `pair_analyzer.py` |

## Key files

- [`src/infrastructure/validators/rhyme/phonetic_validator.py`](../../src/infrastructure/validators/rhyme/phonetic_validator.py) — `PhoneticRhymeValidator` (aggregation + threshold)
- [`src/infrastructure/validators/rhyme/pair_analyzer.py`](../../src/infrastructure/validators/rhyme/pair_analyzer.py) — `PhoneticRhymePairAnalyzer` (pair → score + clausula + precision)
- [`src/infrastructure/validators/rhyme/scheme_extractor.py`](../../src/infrastructure/validators/rhyme/scheme_extractor.py) — `StandardRhymeSchemeExtractor` (scheme → index pairs, supports ABAB / AABB / ABBA / AAAA + arbitrary letter patterns)
- [`src/infrastructure/phonetics/ukrainian_ipa_transcriber.py`](../../src/infrastructure/phonetics/ukrainian_ipa_transcriber.py) — `UkrainianIpaTranscriber` (Cyrillic → IPA, `vowel_positions`, `rhyme_part`)
- [`src/domain/value_objects.py`](../../src/domain/value_objects.py) — `ClausulaType` and `RhymePrecision` enums
- [`src/domain/models/feedback.py`](../../src/domain/models/feedback.py) — `PairFeedback` DTO (note: moved from `src/domain/feedback.py`)
- [`src/shared/string_distance.py`](../../src/shared/string_distance.py) — Levenshtein
- [`src/infrastructure/composition/validation.py`](../../src/infrastructure/composition/validation.py) — DI wiring of pair analyser, scheme extractor, validator

## Caveats and limitations

- **Imperfect IPA transcription.** Rules are simplified: we don't model assimilation (*вокзал* = `[voɡzal]` in reality but transcribes to `[voksal]`), unstressed reduction `[o → ɔ̯]`, etc. For comparative purposes it's enough.
- **Stress is the weak link.** If the Stressifier places stress where the poet didn't intend, the clausula will be cut wrong → the rhyme may pass as valid or fail incorrectly. Especially on rare and loan words.
- **Monorhyme AAAA.** 6 pairs per stanza instead of 2 — the generator has a harder task, and a single bad pair slams accuracy hard.
- **Threshold 0.55** is experimentally chosen. Lower — approves accidental coincidences as rhymes. Higher — rejects classical inexact rhymes.
- **Left-aligned, no trimming.** Since rhyme parts are compared from the stressed vowel over their full length, words with stress at very different depths (e.g. dactylic «ши́бочках» vs feminine «селу́») naturally score lower. This is by design: a real rhyme requires the post-stress sequences to align in length and content.

## See also

- [`stress_and_syllables.md`](./stress_and_syllables.md) — foundation for clausula extraction.
- [`meter_validation.md`](./meter_validation.md) — the other "half" of poem validation.
- [`feedback_loop.md`](./feedback_loop.md) — how rhyme violations flow into corrections.
- [`detection_algorithm.md`](./detection_algorithm.md) — the reverse problem: auto-detect rhyme scheme.
