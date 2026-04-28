# Ukrainian poetry generation system — reader's overview

> This document is neither code nor an ADR. It's meant for an instructor, a reviewer, or a curious reader who wants to understand **what the system is, how it works, and why it was built this way** — without diving into implementation details.

---

## 1. What the system does

Short version: the user supplies a **theme** (say, "spring in a forest"), a **metre** (iamb, trochee, dactyl, amphibrach, anapest), the **foot count** per line, and a **rhyme scheme** (ABAB, AABB, ABBA, AAAA). The system produces a four-line stanza (or several) in Ukrainian that **simultaneously**:

1. matches the theme semantically,
2. follows the requested metre,
3. rhymes per the scheme,
4. is written in grammatically correct Ukrainian with no Latin letters, digits, or technical artefacts.

If the poem fails validation, the system **itself** asks the LLM to fix the offending lines — quoting the specific violations — and repeats the loop up to 3 times.

## 2. Where the idea came from

A capable LLM (Google Gemini) **can** write poetry. The issue: "can" ≠ "does so consistently". Especially for structured constraints like Ukrainian metre + rhyme. Large language models are great at content but routinely slip on technical details: wrong stress, wrong rhyme, one syllable too many or too few.

The standard academic answer is **RAG** — Retrieval-Augmented Generation. We feed the model:

1. **Two real Ukrainian poems on a close theme** — so it understands the subject and how real literature sounds.
2. **Two examples with the correct metre and rhyme** — so it sees the structural template.

Plus, we **validate the model's output** technically (metre, rhyme) and ask it to **fix errors** when they occur. Our code calls this cycle the *feedback loop*.

## 3. The major building blocks

```
                       THEME, METRE, RHYME SCHEME
                                │
                                ▼
    ┌───────────────────────────────────────────────┐
    │            CONTEXT RETRIEVAL (RAG)            │
    │  • 2 thematically close poems from corpus     │
    │  • 2 metre + rhyme reference examples         │
    └───────────────────────────────────────────────┘
                                │
                                ▼
    ┌───────────────────────────────────────────────┐
    │          PROMPT CONSTRUCTION                  │
    │  theme + examples + instructions + rules      │
    └───────────────────────────────────────────────┘
                                │
                                ▼
    ┌───────────────────────────────────────────────┐
    │              GEMINI CALL                      │
    │   (guarded: retry, timeout, logging)          │
    └───────────────────────────────────────────────┘
                                │
                                ▼
    ┌───────────────────────────────────────────────┐
    │         MODEL OUTPUT SANITIZATION             │
    │ • extract content between <POEM>…</POEM>      │
    │ • drop non-Cyrillic / scansion / commentary   │
    └───────────────────────────────────────────────┘
                                │
                                ▼
    ┌───────────────────────────────────────────────┐
    │              POEM VALIDATION                  │
    │  • metre (stress)    • rhyme (phonetic)       │
    └───────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
             ALL GOOD             VIOLATIONS PRESENT
                 │                       │
                 │                       ▼
                 │          ┌────────────────────────┐
                 │          │  ASK LLM TO FIX ONLY    │
                 │          │   the flagged lines     │
                 │          └────────────────────────┘
                 │                       │
                 │           ◄───────────┘ (up to 3 times)
                 ▼
            FINAL POEM
```

## 4. How the system "understands" the theme

Semantic matching. For every poem in our **Ukrainian poetry corpus** (several thousand excerpts from Shevchenko, Lesya Ukrainka, Franko, modern authors) we pre-compute a **semantic vector** — a 768-dimensional numeric representation of meaning. We use the open-source Google LaBSE model (Language-agnostic BERT Sentence Embedding), which works for 100+ languages.

When a request like "spring in a forest" arrives, the system computes the same kind of vector for the theme and uses **cosine similarity** to pick the 5 closest poems from the corpus. The two best ones are injected into the prompt as inspiration: *"look, here's how Ukrainian poets wrote about something close to this."*

Important: the model **does not copy** these examples — they're style and tone, not source text for plagiarism. That's explicitly stated in the instructions.

## 5. How the system checks metre

Metre is the rhythmic alternation of stressed and unstressed syllables. For example, **iamb** = "unstressed-stressed-unstressed-stressed…": *"Sadok vyshnevyi kolo khaty"* (T. Shevchenko).

To check metre the system:

1. **Splits the line into words**.
2. **Finds each word's stress** via a dictionary (`ukrainian-word-stress`, an NLP-powered library). Missing words fall back to a linguistic heuristic (in Ukrainian most words with a soft ending stress the penultimate syllable, those with a hard consonant stress the last).
3. **Builds the actual rhythmic pattern**: a sequence of "unstressed (u) — stressed (—)".
4. **Compares** it against the expected pattern for the requested metre + foot count.
5. **Tolerates minor deviations**: pyrrhic (an unstressed foot), spondee (an extra stress), catalexis (dropped final syllable) — all known prosody variations.

If a line has more than 2 "real" errors, it's invalid. The poem's metric accuracy = the fraction of valid lines.

## 6. How the system checks rhymes

Rhyme is the sound similarity of two line endings — *phonetic*, not orthographic. "Spite" and "spite" are trivial rhymes (identical words); "night" / "light" is a real rhyme: different words with similar-sounding endings.

To check **phonetically** (by sound, not spelling), the system:

1. **Pulls rhyme pairs from the scheme.** For ABAB that's lines 1↔3 and 2↔4; for AABB — 1↔2 and 3↔4; etc.
2. **Extracts the line ending** (the clausula) — the region from the stressed syllable of the final word to the line's end.
3. **Transcribes the clausula to IPA** (International Phonetic Alphabet) — abstract notation of actual sounds. E.g. "я" may be [a] or [ja] depending on context; IPA disambiguates.
4. **Computes normalised Levenshtein similarity** — a math metric "how many character edits turn one string into another". Here it yields a number from 0 (nothing in common) to 1 (identical).
5. **Classifies the rhyme type**:
   - ≥ 0.95 → **exact** rhyme
   - vowels match, consonants diverge → **assonance**
   - consonants match, vowels diverge → **consonance**
   - > 0.0 but below thresholds → **inexact** rhyme
   - 0.0 → **none**

The success threshold defaults to 0.55: a line pair counts as rhyming if similarity ≥ 55%. The poem's rhyme accuracy = the fraction of successful pairs.

## 7. What happens when the poem fails

When metre or rhyme finds violations, the **feedback loop** kicks in. The LLM is sent:

- the current poem with **line numbers** (1, 2, 3, 4),
- a **list of concrete violations**: "Line 2 is 1 syllable longer than expected", "Pair 1–3 low phonetic similarity".

The request is framed so the model **fixes only the flagged lines** and leaves the rest untouched. On success, the system splices the new lines in. On failure — repeats (default up to 3 iterations).

Every iteration's result is preserved for tracing: the UI shows how the poem evolved, what metric and rhyme scores looked like at each step.

## 8. The research side: ablations

Separate from production mode, the system includes an **Evaluation Harness** — a research engine that runs automated experiments. It contains:

- **18 scenarios** (Normal — typical, Edge — boundary cases, Corner — hard / intentionally broken),
- **8 configurations** (A — bare baseline, nothing extra; E — full system with every module; B, C, D — intermediate with feedback; F, G, H — same enrichments but without feedback, for measuring raw component contribution).

A full sweep of 18 × 8 = 144 runs makes it possible to **quantitatively measure** how much each component (semantic RAG, metric examples, feedback loop) contributes to final quality. This is the standard *ablation study* approach in ML/NLP.

Each run is captured in JSON + Markdown reports, with per-config comparison tables and final poems for every setup.

## 9. What the system is designed to do — and what it is not

**Can:**
- Generate correct Ukrainian poems on arbitrary themes (given a Gemini API key).
- Validate metre and rhyme of any supplied poem (without generation).
- Auto-detect metre and rhyme of a pasted poem (brute-force sweep across all 30 metre × foot-count combinations — 5 metres × foot counts 1..6 — and all 4 rhyme schemes).
- Display a full trace: which examples were retrieved, what the model said first, after each iteration, what scores came out.
- Run without an API key in mock mode for pipeline testing.

**Does not:**
- Does not write arbitrary forms (for now — quatrain-based stanzas only).
- Does not support classical ancient metres (hexameter, logaoedic) — only the five canonical Ukrainian metres.
- Does not assess "literary quality" or emotion — only technical conformance to parameters.

## 10. Where to read next

This overview is the 40,000-foot view. The deeper levels, in order of detail:

0. [`user_guide.md`](./user_guide.md) — **end-user documentation**: web UI pages, input limits, time and cost per request, error catalogue, what the system cannot do.
1. [`system_overview.md`](./system_overview.md) — the 16-section system review: architectural layers, each component.
2. [`detection_algorithm.md`](./detection_algorithm.md) — algorithm for auto-detecting metre and rhyme in a pasted poem.
3. [`meter_validation.md`](./meter_validation.md), [`rhyme_validation.md`](./rhyme_validation.md), [`stress_and_syllables.md`](./stress_and_syllables.md) — details of the three core algorithms.
4. [`semantic_retrieval.md`](./semantic_retrieval.md) — how RAG works.
5. [`prompt_construction.md`](./prompt_construction.md) — how the LLM prompt is assembled.
6. [`feedback_loop.md`](./feedback_loop.md) — how the correction loop runs.
7. [`sanitization_pipeline.md`](./sanitization_pipeline.md), [`llm_decorator_stack.md`](./llm_decorator_stack.md) — how model output is scrubbed and how the system reliably connects to Gemini.
8. [`evaluation_harness.md`](./evaluation_harness.md) — the research layer: scenarios, ablations, metrics.
9. [`reliability_and_config.md`](./reliability_and_config.md) — configuration, environment variables, troubleshooting.
10. [`adr/`](../adr/) — records of architectural decisions.
