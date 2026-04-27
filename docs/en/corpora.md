# Poetry corpora — theme and metric-rhyme references

> Two static linguistic resources the system uses for **retrieval-augmented prompting**: the *theme* corpus (semantic guidance — "write something thematically like this") and the *metric-rhyme* corpus (structural guidance — "follow this rhythm and rhyme template"). They are independent, built differently, and consumed by different pipeline stages.

This document describes **what is in each corpus**, **why** it exists, and **how it is constructed**. For the runtime side — how retrieval consumes them — see [`semantic_retrieval.md`](./semantic_retrieval.md) and [`prompt_construction.md`](./prompt_construction.md).

---

## At a glance

| Corpus | File | Records | Source | Used by |
|---|---|---|---|---|
| **Theme reference** | [`corpus/uk_theme_reference_corpus.json`](../../corpus/uk_theme_reference_corpus.json) | 153 poems with 768-dim LaBSE embeddings | Curated authors under `data/` | `RetrievalStage` → semantic top-k by theme |
| **Metric-rhyme reference** | [`corpus/uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) | 193 verified examples (5 metres × 1–6 feet × 4 rhyme schemes; 81 unique combos) | Hand-curated + balanced | `MetricExamplesStage` → exact (metre, feet, scheme) match |
| **Auto-detected metric** *(sibling — built on demand)* | [`corpus/uk_auto_metric_corpus.json`](../../corpus/uk_auto_metric_corpus.json) | Variable; produced by brute-force detection over `data/` | `BuildMetricCorpusRunner` | Optional drop-in replacement for the curated metric corpus |

Both corpora are **static linguistic resources, not training data**. The LLM is never fine-tuned on them — they are dropped into the prompt as few-shot examples each time generation runs.

---

## Theme reference corpus

### Goal

When a user asks for a poem about, say, *"spring in a forest, awakening of nature"*, the LLM benefits from seeing a couple of real Ukrainian poems on a similar theme. The theme corpus is the haystack we search by **semantic similarity**: embed the user's theme with LaBSE, embed every poem in the corpus once at build time, then return the closest-matching poems to inject into the prompt.

The retriever does **not** classify poems by topic and the corpus does **not** carry hand-written topic labels — `approx_theme` is an empty placeholder in the current build. All thematic similarity comes from the LaBSE vector space (multilingual sentence-transformer, 768-dim, normalised).

### What it contains (snapshot of current build)

- **153 poems**, every record carries a 768-dim normalised embedding (`embedding` field).
- **3 526 lines total**, average **23 lines per poem** — full poems, not quatrain excerpts.
- **6 authors**, all classical / 20th-century Ukrainian poetry:

  | Author | Poems |
  |---|---|
  | Леся Українка | 32 |
  | Олег Ольжич | 30 |
  | Володимир Сосюра | 28 |
  | Олена Теліга | 22 |
  | Тарас Шевченко | 21 |
  | Василь Симоненко | 20 |

  This author mix biases retrieval toward **classical and patriotic Ukrainian register**. That is intentional — the system targets formally-correct Ukrainian verse, and the LaBSE-nearest example is more useful when it lives in the same register the user is asking for.

### Record schema

```json
{
  "id":           "local_<author>_<file_stem>_<idx>",
  "text":         "<full poem with newlines>",
  "author":       "<directory name under data/>",
  "approx_theme": [],
  "source":       "local_data",
  "lines":        32,
  "title":        "<poem title from numbered grammar>",
  "path":         "data/<author>/<file>.txt",
  "embedding":    [0.0123, -0.4567, ...]
}
```

- `id` is deterministic and stable across rebuilds — re-running the build over the same `data/` produces the same IDs.
- `approx_theme` is reserved for future hand-labelled topics; today it stays empty and retrieval is purely embedding-driven.
- `embedding` is added by a **separate** runner (`BuildEmbeddingsRunner`) so the build pipeline stays single-purpose. A corpus without embeddings is still a valid input — the offline-deterministic embedder fallback can populate them at runtime if needed.
- The shape is enforced by the `CorpusEntry` `TypedDict` in [`src/domain/models/corpus_entry.py`](../../src/domain/models/corpus_entry.py).

### How it is built

`make build-theme-corpus-with-embeddings` runs the two-step pipeline:

```
┌──────────────────────────────────────────────────────────┐
│ Step 1: BuildCorpusRunner                                │
│   data/<author>/<file>.txt  ──►  PoemFileParser          │
│                                  (numbered-poem grammar) │
│                              ──►  dedup by sha256(text)  │
│                              ──►  uk_theme_reference_corpus.json
├──────────────────────────────────────────────────────────┤
│ Step 2: BuildEmbeddingsRunner                            │
│   uk_theme_reference_corpus.json                         │
│                              ──►  LaBSE encode (batched) │
│                              ──►  embedding[] field      │
│                              ──►  rewrite same JSON      │
└──────────────────────────────────────────────────────────┘
```

#### Step 1 — parsing and deduplication

[`BuildCorpusRunner`](../../src/runners/build_corpus_runner.py) walks `data/`, reads every `.txt`, and delegates parsing to [`PoemFileParser.parse_numbered_poems`](../../src/infrastructure/corpus/poem_file_parser.py). The parser expects a **numbered-poem grammar** — each poem in the source file starts with `<n>. <Title>` followed by the body. The parser:

- normalises whitespace and lowercases the body;
- collapses runs of blank lines (≤ 1 internal blank line preserved);
- skips blocks that fail the `looks_like_poem` heuristic (≥ 4 non-empty lines, ≥ 60 chars, ≤ 10 000 chars, contains Ukrainian Cyrillic letters);
- uses the first body line as a fallback title when the numbered header has no title text.

**Deduplication** is by `sha256(poem.text)` over the full poem body, so reused poems across files appear once. The `id` namespacing (`local_<author>_<file_stem>_<idx>`) is informational only — uniqueness comes from the hash.

The runner enforces a **minimum count** (`--min-count`, default 1) and raises `RepositoryError` when the corpus comes out smaller than the threshold; that prevents silently shipping an empty file in CI.

#### Step 2 — pre-computed embeddings

[`BuildEmbeddingsRunner`](../../src/runners/build_embeddings_runner.py) reads the JSON, **skips poems that already have an `embedding` field** (so the step is idempotent and resumable), loads the LaBSE `SentenceTransformer`, encodes the rest in batches with `normalize_embeddings=True`, rounds to 6 decimals, and writes the JSON back. Pre-computing once at build time means retrieval at request time is a cosine-similarity scan over a numpy array — no model load, no GPU.

#### CLI variables

| Variable | Default | Purpose |
|---|---|---|
| `DATA_DIR` | `data` | Root directory; subfolders become `author` values |
| `THEME_OUT` | `corpus/uk_theme_reference_corpus.json` | Output path |
| `MIN_COUNT` | `1` | Refuse to write a corpus smaller than this |

#### Make targets

```bash
make build-theme-corpus                      # parse + write JSON, no embeddings
make embed-theme-corpus                      # add embeddings to existing JSON (idempotent)
make build-theme-corpus-with-embeddings      # both steps in one go
```

`make embed-theme-corpus` is the recovery path when embeddings are missing or the LaBSE model name changes — it does not re-parse or shuffle the existing records.

---

## Metric-rhyme reference corpus

### Goal

When the user requests *"iamb, 4 feet, ABAB"*, the LLM benefits from seeing a couple of **real Ukrainian poems with exactly that rhythm and rhyme scheme**. Where the theme corpus answers *"what should this poem be about"*, the metric corpus answers *"what should this poem sound like"*. Pipeline stage [`MetricExamplesStage`](../../src/infrastructure/stages/metric_examples_stage.py) does an exact lookup on `(metre, feet, scheme)`, picks the top-k entries, and the prompt builder prepends them.

### What it contains (snapshot of current build)

- **193 records**, all flagged `verified=True` (the corpus is human-validated, not auto-detected).
- **Average 6.7 lines per record** — typically a single quatrain or two. Snippets, not full poems.
- **5 metres × 1–6 feet × 4 rhyme schemes = 81 distinct `(metre, feet, scheme)` combinations** filled out of a 120-cell theoretical grid.
- Most cells carry **at least 2 examples** so the few-shot prompt has a choice of register; popular cells have many more (`ямб 5ст ABAB`: 14, `анапест 3ст ABAB`: 12, `ямб 4ст ABAB`: 7).
- **77 of 193** records carry an explicit author (Леся Українка, Сосюра, Шевченко, Тичина, Костенко, Сковорода, Чумак, Антонич, Симоненко, Олесь, Філянський, Бажан, …); the remaining 116 are **synthetic / re-combined balanced examples** added by hand to fill cells the classical sources did not cover.
- **151 of 193** carry a free-text `note` explaining the scansion or the rhyme classification.
- **35 of 193** carry an explicit `stress_pattern` (binary string `010101…`) — kept where the metre is non-obvious and the editor wanted to lock the canonical reading.

#### Coverage by metre × scheme

|        | ABAB | AABB | ABBA | AAAA |
|--------|------|------|------|------|
| ямб        | 25 | 10 |  8 |  8 |
| хорей      | 10 |  8 |  8 |  8 |
| дактиль    |  8 | 10 |  8 |  8 |
| амфібрахій |  8 |  8 |  6 |  6 |
| анапест    | 20 |  8 | 10 |  8 |

#### Coverage by feet × scheme

|       | ABAB | AABB | ABBA | AAAA |
|-------|------|------|------|------|
| 1ст   |  2 | 0 | 0 | 0 |
| 2ст   |  6 | 6 | 4 | 4 |
| 3ст   | 22 | 10 | 10 | 10 |
| 4ст   | 15 | 12 | 10 | 10 |
| 5ст   | 22 | 10 | 10 | 10 |
| 6ст   |  4 |  6 |  6 |  4 |

The 1-foot row is sparse on purpose — 1-foot anapest exists in `corpus/uk_metric-rhyme_reference_corpus.json` for the C05 evaluation scenario but is otherwise an extreme corner case. 6-foot lines are also fewer because the alexandrine register is rarer in the source authors.

### Record schema

```json
{
  "id":             "iamb_3_ABAB",
  "meter":          "ямб",
  "feet":           3,
  "scheme":         "ABAB",
  "stress_pattern": "010101",
  "verified":       true,
  "source":         "Василь Чумак, перший катрен вірша «Заквіт осінній сум»",
  "author":         "Василь Чумак",
  "title":          "Заквіт осінній сум",
  "note":           "Скандування: за-КВІТ-о-СІН-ній-СУМ = UÚ UÚ UÚ → ямб 3ст. Рима ABAB: …",
  "text":           "Заквіт осінній сум,\nОсінній сум заквіт.\nНа віях я несу\nГаптований привіт."
}
```

- `id` follows the pattern `<metre>_<feet>_<scheme>[_<author>_<file>_<idx>]` — the bare prefix is reserved for the canonical "first example" of each cell.
- `stress_pattern` is the binary canonical pattern (`0` = unstressed, `1` = stressed) without weak-stress / pyrrhic exceptions; used for fast lookup, not full validation.
- `note` is intentionally informal — it is editor commentary the dashboard does not render but reviewers consult.
- The shape is enforced by the `MetricCorpusEntry` `TypedDict` in [`src/domain/models/metric_corpus_entry.py`](../../src/domain/models/metric_corpus_entry.py).

### How it was constructed

Unlike the theme corpus, the metric-rhyme corpus is **not produced by a runner**. It was built by hand and is checked into the repository. The construction methodology was:

1. **Seed from canonical poetry.** For each `(metre, feet, scheme)` cell, find a real quatrain by a recognisable Ukrainian poet that satisfies the cell exactly. The first records (e.g. `iamb_3_ABAB` from Василь Чумак's «Заквіт осінній сум») are these seeds — they have explicit `author`, `source`, and a `note` documenting the scansion.
2. **Verify by validation.** Each seed is run through `PatternMeterValidator` and `PhoneticRhymeValidator`; only quatrains that pass with `accuracy ≥ threshold` are kept. The `verified=True` flag is the editorial promise that this happened.
3. **Balance the matrix.** Cells classical authors did not naturally fill (e.g. 1-foot, AAAA monorhyme, 6-foot non-alexandrine) were filled with **synthetic balanced examples**: hand-written quatrains, or re-combined lines from classical authors, or small variations on existing examples. Their `author` field is `""` or marked `"синтетичний приклад"` / `"<author> (рядки перекомбіновані)"` and they all still pass validation.
4. **Document the edge cases.** Where the metre is ambiguous (one syllable could be read either way, an enclitic clitic shifts stress, etc.), the editor adds a `note` explaining which reading the corpus enforces. This is what `note` is for — it is not displayed at runtime but it lets the next maintainer understand the editorial choice.

The entry in [`src/infrastructure/repositories/metric_repository.py`](../../src/infrastructure/repositories/metric_repository.py) is the only consumer; it reads the JSON eagerly at build-container time and exposes `find_examples(query, k)` which scans for exact `(metre, feet, scheme)` match and returns up to `k` rows.

### Why `verified=True` everywhere

The flag exists for the **auto-detected sibling** corpus described next. In `uk_metric-rhyme_reference_corpus.json` every record is human-verified, so the flag is a no-op tautology. It is kept on the records as a forward-compat marker so any downstream code that ever merges the curated and auto-detected corpora can filter on it.

---

## Sibling: auto-detected metric corpus

[`corpus/uk_auto_metric_corpus.json`](../../corpus/uk_auto_metric_corpus.json) is **built on demand** from `data/` and is *not* checked in as a primary resource. It exists for two reasons:

- **Validating the detection algorithm** end-to-end against a larger sample than the curated set covers — every poem under `data/` becomes a labelling target.
- **A larger pool of structural examples** when the curated corpus is too thin for an experimental cell.

### How it is built — `make build-metric-corpus`

[`BuildMetricCorpusRunner`](../../src/runners/build_metric_corpus_runner.py) walks the same `data/` tree the theme builder uses, parses each file with `PoemFileParser`, then runs each poem through `IDetectionService` (brute-force `(metre, feet, scheme)` enumeration — see [`detection_algorithm.md`](./detection_algorithm.md)).

Three outcomes per poem:

1. **Both metre and rhyme detected** with sufficient accuracy → record goes into `uk_auto_metric_corpus.json`. `verified=False` (this is auto-detection, not human review). `meter_accuracy` and `rhyme_accuracy` are stored on the record so a consumer can filter or rank.
2. **Partial detection** (only metre OR only rhyme passes the threshold) → record goes into a sidecar `uk_auto_metric_corpus_drafts.json` with `source="auto-detected-partial"`. These are the borderline poems an editor might promote to the curated corpus after manual scansion.
3. **Nothing detected** → poem is skipped, only logged.

The drafts file is deleted automatically when no partial detections occurred, so a clean run leaves only the canonical artifact behind. Both the corpus and the drafts file are deduped by `sha256(poem.text)`, the same as the theme builder.

### Record schema differences

```json
{
  "id":              "ямб_4_ABAB_тарас-шевченко_тарас-шевченко-1_3",
  "meter":           "ямб",
  "feet":            4,
  "scheme":          "ABAB",
  "meter_accuracy":  0.9375,
  "rhyme_accuracy":  1.0,
  "verified":        false,
  "source":          "auto-detected",
  "author":          "тарас-шевченко",
  "title":           "<poem title>",
  "text":            "<full poem>"
}
```

Three fields differ from the curated schema:

- `meter_accuracy` and `rhyme_accuracy` are present (auto-detection is graded, not binary).
- `verified` is `false`.
- `note` and `stress_pattern` are absent (no editor commentary).

---

## Why two corpora and not one

The two retrieval stages have **different definitions of "useful example"**:

- *Theme retrieval* wants the closest semantic neighbour regardless of metre. A poem with the same theme written in a different metre is still useful — the LLM picks up imagery, register, and lexicon, not rhythm.
- *Metric examples* want the closest structural neighbour regardless of theme. A poem about an utterly unrelated topic is fine if it teaches the LLM the metre+rhyme template by example.

Merging them into one corpus would force every record to be useful in both senses, which is rare. Keeping them separate lets each retrieval stage optimise for its own dimension and lets the ablation harness measure their contributions independently (configs C, D, E in [`evaluation_harness.md`](./evaluation_harness.md)).

---

## Key files

- [`scripts/build_corpus_from_data_dir.py`](../../scripts/build_corpus_from_data_dir.py) — argparse wrapper for the theme builder; chains the embeddings step on `--embed`.
- [`scripts/build_corpus_embeddings.py`](../../scripts/build_corpus_embeddings.py) — argparse wrapper for the embeddings runner.
- [`scripts/build_metric_corpus.py`](../../scripts/build_metric_corpus.py) — argparse wrapper for the auto-detected metric builder.
- [`src/runners/build_corpus_runner.py`](../../src/runners/build_corpus_runner.py) — `IRunner` that turns `data/` into the theme JSON.
- [`src/runners/build_embeddings_runner.py`](../../src/runners/build_embeddings_runner.py) — `IRunner` that pre-computes LaBSE vectors.
- [`src/runners/build_metric_corpus_runner.py`](../../src/runners/build_metric_corpus_runner.py) — `IRunner` for the auto-detected metric corpus.
- [`src/infrastructure/corpus/poem_file_parser.py`](../../src/infrastructure/corpus/poem_file_parser.py) — numbered-poem grammar parser shared by both builders.
- [`src/domain/models/corpus_entry.py`](../../src/domain/models/corpus_entry.py) — `CorpusEntry` `TypedDict` (theme schema).
- [`src/domain/models/metric_corpus_entry.py`](../../src/domain/models/metric_corpus_entry.py) — `MetricCorpusEntry` `TypedDict` (auto-detected schema).
- [`src/infrastructure/repositories/theme_repository.py`](../../src/infrastructure/repositories/theme_repository.py) — runtime reader for the theme JSON (`JsonThemeRepository`, `DemoThemeRepository`).
- [`src/infrastructure/repositories/metric_repository.py`](../../src/infrastructure/repositories/metric_repository.py) — runtime reader for the metric-rhyme corpus.
- [`Makefile:206-257`](../../Makefile#L206) — `make build-theme-corpus`, `embed-theme-corpus`, `build-theme-corpus-with-embeddings`, `build-metric-corpus`.

---

## Caveats

- **The repository ships pre-built corpora.** You normally do not need to rebuild the theme corpus — running `make build-theme-corpus-with-embeddings` overwrites the checked-in `corpus/uk_theme_reference_corpus.json` with whatever is currently under `data/`. Rebuild only when you change `data/` or want to recompute embeddings against a different LaBSE model.
- **The metric-rhyme reference corpus is editorial.** Re-deriving it from `data/` will *not* produce the same file — that one is hand-curated and balanced. Use `make build-metric-corpus` to produce the *auto-detected* sibling, never to "rebuild" the curated reference.
- **Author bias is intentional.** Six classical Ukrainian authors is enough for the system's target register. Adding modern poetry would dilute the LaBSE neighbourhood and likely surface in the ablation report as a regression on `semantic_relevance` for classical themes.
- **Embeddings are fragile to model changes.** Re-running `make embed-theme-corpus` after switching `LABSE_MODEL` rewrites every record's `embedding` field. Pre-existing retrieval caches that pinned a previous vector space stop matching — the simplest recovery is to delete `corpus/*.json` embeddings and let the runner recompute.
