# Semantic retrieval (RAG)

> How the system finds a handful of thematically close poems in the corpus and injects them into the prompt as inspiration. This is Retrieval-Augmented Generation applied to Ukrainian poetry.

## Why

Prompt without context: *"Write a poem about spring."* The model produces a generic poem, often templated, unconnected to Ukrainian tradition.

Prompt with RAG: *"Write a poem about spring. Here are two Ukrainian poetry excerpts about something close: [Shevchenko], [Tychyna]. Don't copy — take the spirit and tone."* The result hugs Ukrainian literary style, uses natural vocabulary.

Important: we never ask the model to **copy** the examples. They're a **style anchor**. This is stated explicitly in the prompt instructions.

## The idea

For every poem in our corpus we pre-compute a **semantic vector** (embedding) — a numeric representation of meaning in a high-dimensional space. If two poems are semantically close — their vectors are close (small angle between them). If they're far apart — the vectors diverge.

At request time:
1. Convert the theme into the same kind of vector.
2. For every poem in the corpus, compute the cosine of the angle between the theme vector and the poem vector.
3. Sort by descending cosine (1.0 = identical direction, 0.0 = perpendicular).
4. Take the **5 closest** (top-k).

Two of those five (or a different number per configuration) are injected into the prompt as thematic examples.

## The embedding model: LaBSE

We use [`sentence-transformers/LaBSE`](https://huggingface.co/sentence-transformers/LaBSE) from Google — Language-agnostic BERT Sentence Embedding. Trained on 109 languages including Ukrainian, on 6 billion translation pairs.

Characteristics:
- **Vector dimension:** 768
- **Normalisation:** vectors are normalised to unit length (`||v|| = 1`). Hence cosine similarity = plain dot product.
- **Model size:** ~1.9 GB. Lazy-loaded on first call via the `sentence-transformers` library.
- **Inference:** works on CPU, ~5-10× faster on GPU. A single poem is sub-second.

Implementation: [`LaBSEEmbedder`](../../src/infrastructure/embeddings/labse.py).

## Architecture with fallback

LaBSE needs the network (HuggingFace download on first run). Not always available: CI without internet, pre-commit hooks, offline development. The composition root therefore wires one of two shapes depending on the `OFFLINE_EMBEDDER` flag (see [`generation_data_plane.py`](../../src/infrastructure/composition/generation_data_plane.py)):

- `OFFLINE_EMBEDDER=true` → the container's `embedder()` returns `OfflineDeterministicEmbedder` directly. No composite layer is built.
- `OFFLINE_EMBEDDER=false` (default) → `CompositeEmbedder(primary=LaBSEEmbedder, fallback=OfflineDeterministicEmbedder)`.

[`CompositeEmbedder`](../../src/infrastructure/embeddings/composite.py) on `encode(text)`:
1. Try primary (LaBSE).
2. On `EmbedderError` (model missing, network down, OOM) → **switch to fallback permanently** for this process. Warning logged once.
3. Subsequent calls go straight to fallback (no retries of primary).

### OfflineDeterministicEmbedder

[`OfflineDeterministicEmbedder`](../../src/infrastructure/embeddings/labse.py) is a fallback that does **no real NLP**. It works like this:

```python
def encode(text: str) -> list[float]:
    rng = random.Random(abs(hash(text)) % (2**32))
    vec = [rng.gauss(0, 1) for _ in range(768)]
    norm = sqrt(sum(x**2 for x in vec))
    return [x / norm for x in vec]
```

Hash → seed for a deterministic RNG → 768 Gaussian numbers → normalise.

Properties:
- **Deterministic:** same text gives the same vector. Tests, CI, regression checks stay stable.
- **No semantic meaning.** Proximity between two vectors is random. In offline mode retrieval **does not** return thematically close poems — it returns the first 5 by hash similarity, which is effectively random.
- **Ideal for unit tests.** The pipeline can be tested end-to-end without depending on a ~2 GB model.

In production this means: **if LaBSE fails, the `semantic_relevance` metric becomes noise**, but the pipeline does not crash — it still produces some output. The log will warn about it.

## The corpus: format and preparation

The corpus is a JSON file ([`corpus/uk_theme_reference_corpus.json`](../../corpus/uk_theme_reference_corpus.json)). Shape:

```json
[
  {
    "id": "shevchenko-0001",
    "text": "Садок вишневий коло хати,\nХрущі над вишнями гудуть,\nПлугатарі з плугами йдуть,\nСпівають ідучи дівчата...",
    "author": "Taras Shevchenko",
    "theme": "village evening, nature",
    "embedding": [0.0134, -0.0072, 0.0456, ...]  // 768 floats
  },
  ...
]
```

**The `embedding` field** is a pre-computed vector. Stored in the corpus so the 1000+ LaBSE calls at request time are avoided. At request time we only encode **the theme** (once) and compare against all stored vectors.

[`JsonThemeRepository.load`](../../src/infrastructure/repositories/theme_repository.py) reads this file and constructs `ThemeExcerpt` records (id, text, author, theme, embedding tuple). When the file is missing the composition root falls back to `DemoThemeRepository` (a tiny hard-coded set of Shevchenko excerpts) — the pipeline still runs, just with degraded retrieval.

Building the corpus is a separate offline workflow exposed via the Makefile:
```bash
make build-theme-corpus DATA_DIR=data/public-domain-poems    # texts only
make build-theme-corpus-with-embeddings                      # texts + LaBSE embeddings
```

The second target is what produces the production-ready `corpus/uk_theme_reference_corpus.json` consumed by `JsonThemeRepository`.

## Retrieval: how ranking actually works

[`SemanticRetriever`](../../src/infrastructure/retrieval/semantic_retriever.py) implements the `IRetriever` port. The actual signature is `retrieve(theme, corpus, top_k=5)`:

```python
class SemanticRetriever(IRetriever):
    def __init__(self, embedder: IEmbedder) -> None:
        self._embedder = embedder

    def retrieve(
        self, theme: str, corpus: list[ThemeExcerpt], top_k: int = 5,
    ) -> list[RetrievedExcerpt]:
        query_vec = self._embedder.encode(theme)
        ranked = sorted(
            (self._score(query_vec, excerpt) for excerpt in corpus),
            key=lambda x: x.similarity,
            reverse=True,
        )
        return ranked[: max(1, top_k)]
```

For each excerpt the retriever uses the pre-computed `excerpt.embedding` if present, otherwise it lazily encodes `excerpt.text`. Cosine similarity is `dot(a, b) / (||a|| * ||b||)`; because LaBSE returns normalised vectors (`||v|| = 1`), this collapses to a plain dot product — a CPU trifle.

Returns `list[RetrievedExcerpt]`:
- `excerpt` — a `ThemeExcerpt` value object with text and metadata.
- `similarity` — a value in `[-1, 1]`, practically in `[0, 1]` for normalised embeddings.

## Pipeline integration

`RetrievalStage` in [`src/infrastructure/stages/retrieval_stage.py`](../../src/infrastructure/stages/retrieval_stage.py):

1. Calls `IThemeRepository.load()` → list of corpus poems.
2. Calls `retriever.retrieve(theme, corpus, top_k=5)`.
3. Stores `state.retrieved` (list of `RetrievedExcerpt`).
4. The next `PromptStage` feeds the excerpts into [`RagPromptBuilder`](../../src/infrastructure/prompts/rag_prompt_builder.py), which injects the top 2 (by default) into the prompt as thematic style anchors.

The retriever, repositories, and embedder are wired in [`generation_data_plane.py`](../../src/infrastructure/composition/generation_data_plane.py); the LLM stack lives in `generation_llm_stack.py`; the pipeline stages themselves are wired in `generation_pipeline_stages.py`.

The search depth (`k=5`) and the injection count (`top_k=2`) are different parameters:
- 5 for diagnostics / UI — useful to see what retrieval picked.
- 2 into the prompt — any more and the prompt gets bloated and the model starts copying.

## Parallel with the metric retriever

There's a **second** retrieval layer — `MetricExamplesStage` — which pulls examples from a separate corpus by metre and rhyme (**not** semantically, but by an exact `meter + foot_count + rhyme` query). This does **not** use embeddings; it's an SQL-like filter query. Details in [`prompt_construction.md`](./prompt_construction.md).

## Key files

- [`src/infrastructure/retrieval/semantic_retriever.py`](../../src/infrastructure/retrieval/semantic_retriever.py) — `SemanticRetriever` (`IRetriever` impl)
- [`src/infrastructure/embeddings/labse.py`](../../src/infrastructure/embeddings/labse.py) — `LaBSEEmbedder` (768-d, sentence-transformers) and `OfflineDeterministicEmbedder` (test/CI fallback)
- [`src/infrastructure/embeddings/composite.py`](../../src/infrastructure/embeddings/composite.py) — `CompositeEmbedder` runtime fallback chain
- [`src/infrastructure/repositories/theme_repository.py`](../../src/infrastructure/repositories/theme_repository.py) — `JsonThemeRepository` / `DemoThemeRepository` / `InMemoryThemeRepository`
- [`src/infrastructure/composition/generation_data_plane.py`](../../src/infrastructure/composition/generation_data_plane.py) — wiring of repositories, embedder (with `OFFLINE_EMBEDDER` switch), retriever
- [`src/infrastructure/stages/retrieval_stage.py`](../../src/infrastructure/stages/retrieval_stage.py) — pipeline integration
- [`corpus/uk_theme_reference_corpus.json`](../../corpus/uk_theme_reference_corpus.json) — the corpus itself (built by `make build-theme-corpus-with-embeddings`)

## Configuration

| Parameter | Where | Default |
|-----------|-------|---------|
| Corpus path | `CORPUS_PATH` (env) | `corpus/uk_theme_reference_corpus.json` |
| Embedding model | `LABSE_MODEL` (env) | `sentence-transformers/LaBSE` |
| Offline mode | `OFFLINE_EMBEDDER=true` | `false` (uses LaBSE) |
| Retrieval top-k | `GenerationRequest.top_k` | `5` |
| Injected into prompt | `GenerationRequest.metric_examples_top_k` (yes, slightly misleading name — applies to thematic too) | `2` |

## Caveats

- **Lazy LaBSE load.** On the first call inside a container ~10-30 s go to model loading. The generation page shows this on the spinner. Subsequent calls are sub-second.
- **HuggingFace cache.** The model is downloaded once and cached in `~/.cache/huggingface/`. The `hf_cache` Docker volume in [`docker-compose.yml`](../../docker/docker-compose.yml) persists it across runs.
- **Corpus quality is critical.** Garbage corpus → garbage examples → garbage generation. That's why there's `MIN_COUNT` and length filtering in the `build-theme-corpus` script.
- **Without a Ukrainian corpus it works, but badly.** The system supports other languages (LaBSE is multilingual), but you'd need to supply the right JSON. With no corpus retrieval returns an empty list → the prompt is built without thematic examples → quality drops.

## See also

- [`prompt_construction.md`](./prompt_construction.md) — how retrieval integrates into the prompt.
- [`evaluation_harness.md`](./evaluation_harness.md) — the `semantic_relevance` metric evaluates how semantically close the final poem remains to the theme.
- [`system_overview_for_readers.md`](./system_overview_for_readers.md) §4 — high-level semantic-retrieval explanation.
