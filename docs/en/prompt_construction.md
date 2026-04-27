# Prompt construction

> Two prompt builders serve two scenarios: initial generation and regeneration in the feedback loop. Both emit in the same format (`<POEM>...</POEM>` envelope), but the contents differ.

## Context layers

Before the model runs, the system assembles several layers of information:

1. **Theme and parameters** — what to generate (theme, metre, foot count, rhyme scheme, stanza count, lines per stanza).
2. **Thematic examples** — up to *k* poems from the corpus semantically close to the theme. The list collapses to empty when the retrieval stage is skipped or finds nothing — the surrounding "Use the following poetic excerpts..." header is still emitted, but with no excerpts beneath it. See [`semantic_retrieval.md`](./semantic_retrieval.md).
3. **Metric-rhyme examples** — up to *k* poems from a separate corpus that **exactly** match the requested metre + feet + scheme. **Fully optional**: when the metric-examples stage is skipped, or the corpus has no matches, the entire metric block (header + examples) is dropped from the prompt. See §"Metric examples" below.
4. **Output envelope format** — `<POEM>…</POEM>` with all the rules.
5. **Prohibitions** — no scansion, no ALL-CAPS, no English, no markdown, no parenthesised syllable numbers, and so on.

For regeneration we also add:

6. **Current poem with line numbers** — `1: line one\n2: line two\n...`
7. **Bullet list of violations** — `- Line 2: 1 syllable longer than expected`, etc.

Whether the optional layers actually appear is decided at pipeline-construction time by [`IStageSkipPolicy`](../../src/infrastructure/pipeline/skip_policy.py): ablation studies and lightweight scenarios can disable retrieval and/or metric examples, and the prompt builder simply receives empty lists, dropping the corresponding blocks.

## Relationship to the LLM call

Prompt construction is the input to a single `ILLMProvider.generate(prompt)` (initial pass) or `ILLMProvider.regenerate_lines(poem, feedback)` (feedback iterations) call. That call goes through the [decorator stack](./llm_decorator_stack.md): logging → retry → timeout → sanitize → extract → real provider. The prompt's `<POEM>...</POEM>` contract is what `SentinelPoemExtractor` later relies on to peel chain-of-thought off the response — see [`sanitization_pipeline.md`](./sanitization_pipeline.md).

## Initial generation prompt (RAG)

[`RagPromptBuilder.build(request, retrieved, examples)`](../../src/infrastructure/prompts/rag_prompt_builder.py) assembles the prompt from the following blocks in order:

### Block 1: thematic examples

```
Use the following poetic excerpts as thematic inspiration (do not copy):

<poem 1>

<poem 2>
```

The "**do not copy**" instruction is critical — without it the model routinely pastes verbatim Shevchenko into the response. The formatter joins examples with `\n\n`.

### Block 2: metric examples (optional)

```
Use these verified examples as METER and RHYME reference (they demonstrate
iamb meter with ABAB rhyme scheme — follow this rhythm and rhyme pattern exactly):

<example 1 with the correct metre+rhyme>

<example 2>
```

Optional: if the metric corpus has nothing for the `(meter, foot_count, rhyme)` tuple, this block is dropped entirely. The wording "**follow this rhythm and rhyme pattern exactly**" replaces "do not copy" — here we actually want the rhythm taken, just not the words.

### Block 3: core instruction

```
Theme: <theme>
Meter: <metre>
Rhyme scheme: <scheme>
Structure: <stanza_count> stanza(s) of <lines_per_stanza> lines each (<total_lines> lines total)
Generate a Ukrainian poem with exactly <total_lines> lines.
```

### Block 4: envelope rules

```
OUTPUT ENVELOPE (mandatory):
Wrap your FINAL poem between the literal tags <POEM> and </POEM>.
You may reason freely BEFORE <POEM>. Everything between <POEM> and </POEM>
must be ONLY clean Ukrainian poem lines in normal orthography — one line
per verse line, exactly <N> lines, no blank separators other than one newline
between lines. Emit </POEM> immediately after the last poem line; write nothing
after it.
```

We deliberately allow the model to "reason aloud before the tag" — those five tokens give reasoning models (Gemini 2.5+) a CoT channel to unload. Without it they still reason, but try to hide it, producing muddled output.

### Block 5: strict format rules

```
STRICT FORMAT RULES FOR THE CONTENT BETWEEN <POEM>...</POEM>:
- The first token after <POEM> MUST be a Cyrillic letter.
- Every output line MUST contain Ukrainian words; lines with only
  punctuation/digits/scansion are forbidden.
- NO ALL-CAPS words marking stress (forbidden: 'І-ДУТЬ', 'БІЙ').
- NO syllable hyphenation inside words (forbidden: 'За-гу-бив-ся').
- NO syllable numbering in parentheses (forbidden: 'Слу(1) жи(2)').
- NO scansion marks ('u u -', '( - )', '(U)', '->').
- NO bare number sequences like '1 2 3 4 5 6 7 8'.
- NO English words, commentary, analysis, drafts, alternatives, markdown,
  bullets, line numbers, or explanations between the tags.
```

These prohibitions duplicate the sanitizer's job — the model still ignores some of them, but an explicit statement cuts issues by ~60%.

## Regeneration prompt (feedback loop)

[`NumberedLinesRegenerationPromptBuilder.build(poem, feedback_messages)`](../../src/infrastructure/prompts/regeneration_prompt_builder.py):

### Block 1: instruction

```
You are given a Ukrainian poem with line numbers and a list of violations.
Fix ONLY the lines mentioned in the feedback. Copy all other lines exactly
unchanged.
Return the COMPLETE poem — every line, in the correct order — with no line
numbers, no commentary, no markdown.
```

"Return the COMPLETE poem" + "no line numbers" is the key pair: we pass numbering as a visual hint, but want a clean poem back.

### Block 2: envelope (identical to the RAG version)

Same block about `<POEM>…</POEM>`.

### Block 3: strict format rules (shorter version)

Same prohibitions as RAG.

### Block 4: feedback note

```
IMPORTANT: the violations below may reference stress positions and syllable
counts to explain WHAT is wrong. Do NOT copy that notation into your output.
Your output must be plain Ukrainian poem lines in normal orthography — NO
ALL-CAPS words, NO hyphenated syllables ('За-гу-бив-ся'), NO parenthesized
syllable numbers ('сло(1) во(2)'), NO scansion marks ('u u -', '(U)'), NO
bare digit sequences, NO English commentary.
```

This block exists **specifically because** the model loves to copy scansion from feedback into the output. Repeating the warning helps, but not 100%.

### Block 5: numbered poem

```
POEM (with line numbers for reference):
1: Спинися, мить, на цім порозі,
2: Де тихо світяться вогні.
3: Замри на зоряній дорозі,
4: Навій чарівний сон мені.
```

Format: `{i+1}: {line}` — 1-based numbering for readability.

### Block 6: bullet list of violations

```
VIOLATIONS TO FIX:
- Line 2: 1 syllable longer than expected (iamb, 4 feet → 8 syllables)
- Pair 1–3: phonetic similarity 0.45, below threshold 0.55
```

Messages are formatted by [`UkrainianFeedbackFormatter`](../../src/infrastructure/feedback/ukrainian_formatter.py) from structural `LineFeedback` / `PairFeedback` objects. Language — Ukrainian (so the model better understands Ukrainian linguistic terminology), but descriptions are neutral without scansion notation.

## Metric examples — how they are picked

A separate corpus [`corpus/uk_metric-rhyme_reference_corpus.json`](../../corpus/uk_metric-rhyme_reference_corpus.json) contains poems with **metre and rhyme tags**. Every record has `meter`, `foot_count`, `rhyme_scheme` fields.

[`JsonMetricRepository.find(meter, foot_count, rhyme_scheme, top_k=2)`](../../src/infrastructure/repositories/metric_repository.py):

1. Filter: take all records where `meter`, `foot_count`, `rhyme_scheme` all match.
2. If ≥ top_k found — take the first top_k (by file order; switch to random sampling if desired).
3. If < top_k found — take what's there (can be 0).

No semantic similarity involved — it's a **parametric exact-match query**. This corpus is built separately via `make build-metric-corpus`, which runs a corpus of poems through auto-detection (see [`detection_algorithm.md`](./detection_algorithm.md)) and keeps poems whose detected metre and rhyme match their tags.

For combinations with no examples (rare: *6-foot anapest AAAA*), the pipeline proceeds without the metric-examples block. That's one of the Edge scenarios in the evaluation harness (E03).

## Sanitizer cooperation

The prompts carefully phrase the prohibitions, **but don't rely on full model obedience**. The "clean output" responsibility is split:

1. **Prompt** lowers breakage probability: told what not to do, the model mostly tries.
2. **Sanitizer** catches whatever slips through anyway. See [`sanitization_pipeline.md`](./sanitization_pipeline.md).

This is a belt-and-suspenders approach — no single layer was reliable on its own.

## Key files

- [`src/infrastructure/prompts/rag_prompt_builder.py`](../../src/infrastructure/prompts/rag_prompt_builder.py) — RAG prompt for initial generation
- [`src/infrastructure/prompts/regeneration_prompt_builder.py`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) — feedback-driven regeneration prompt
- [`src/infrastructure/feedback/ukrainian_formatter.py`](../../src/infrastructure/feedback/ukrainian_formatter.py) — Ukrainian violation-message formatter
- [`src/infrastructure/repositories/metric_repository.py`](../../src/infrastructure/repositories/metric_repository.py) — parametric search for metric examples
- [`src/infrastructure/llm/gemini.py`](../../src/infrastructure/llm/gemini.py) — system prompt duplicating envelope rules in `system_instruction` for the Gemini API

## Caveats

- **Gemini system prompt.** `GeminiProvider` has a dedicated `system_instruction` with the same envelope rules. This is not duplication — the system prompt has higher priority in the Gemini API and influences every call. The user prompt (RAG/regeneration) is the context of the specific request.
- **Prompt length.** A typical RAG prompt is 600-2500 characters. Exceeds 4 k tokens only with very long thematic examples (which we don't take).
- **"Do not copy" is a pivotal phrase.** Without it the model routinely pastes excerpts verbatim into the response. With it — not perfect, but much better.
- **Numbering format** in regeneration — `1: line` rather than `1. line` (a period could be part of a real line).
- **Feedback text** is in Ukrainian but scansion-free. This reduces the chance of the model copying notation (which would be English: `u - u -`).

## See also

- [`semantic_retrieval.md`](./semantic_retrieval.md) — where thematic examples come from.
- [`sanitization_pipeline.md`](./sanitization_pipeline.md) — how output is cleaned.
- [`feedback_loop.md`](./feedback_loop.md) — how the regeneration prompt weaves into the full cycle.
- [`reliability_and_config.md`](./reliability_and_config.md) — env parameters that shape the prompt (model, max_tokens, temperature).
