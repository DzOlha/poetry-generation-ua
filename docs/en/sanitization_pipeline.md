# LLM output sanitization

> How the system extracts and cleans the poem from the raw model output. Two complementary stages: **tag-based extraction** + **allowlist sanitization**.

## Problem

Reasoning models (Gemini 2.5+ / 3.x Pro) emit large chain-of-thought that can leak:

- English reasoning: `"Let's try:"`, `"Perfect dactyl!"`, `"Wait, "мої" -> мо-Ї."`.
- Stress notation: `КрОки`, `тІ(4)`, `(u - u - u -)`.
- Syllable hyphenation: `за-гу-бив-ся`, `о-бе-рЕж-ні`.
- Parenthesized syllable numbers: `Слу(1) жи(2) ли(3)`.
- Bare digit sequences: `1 2 3 | 4 5 6 | 7 8`.
- Bullets / markdown: `* C2:`, `// comment`.
- Truncated-output fragments: `).`, `,.`, empty lines.

All of this reaches the validator → misleading metrics, wasted iterations, ugly UI.

## Two-layer strategy

### Layer 1 — Sentinel extractor

The model is **asked** to wrap the final poem between tags:

```
<POEM>
Тихо спить у місті ніч
Ліхтарі горять в імлі
</POEM>
```

The instruction lives in [rag_prompt_builder.py](../../src/infrastructure/prompts/rag_prompt_builder.py), [regeneration_prompt_builder.py](../../src/infrastructure/prompts/regeneration_prompt_builder.py), plus the Gemini system prompt ([gemini.py](../../src/infrastructure/llm/gemini.py)).

[`SentinelPoemExtractor`](../../src/infrastructure/sanitization/sentinel_poem_extractor.py) is tolerant of realistic model failures:

- **Multiple `<POEM>` blocks** → take the **last** (often a final revision after CoT).
- **Opening tag without closing** → take everything after the last `<POEM>` (`max_tokens`-truncated output).
- **Empty block `<POEM></POEM>`** → pass input through unchanged (let the sanitizer salvage).
- **No tags at all** → pass input through unchanged. Don't fail — the model sometimes skips tags, and the sanitizer still has a shot at pulling the poem out of raw CoT.

Matching is case-insensitive: `<poem>` / `<Poem>` also work.

### Layer 2 — Allowlist sanitization

[`RegexPoemOutputSanitizer`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py) takes the extractor output and drops **lines** that violate the rules.

The approach is **allowlist-first, not blacklist**: every character on a line must be in the permitted set. Everything else is garbage.

**Allowed characters:**

- Ukrainian Cyrillic: А-Я, а-я, І, Ї, Є, Ґ (and lowercase)
- Combining acute `\u0301` (stress marker)
- Apostrophe: `'`, `’`, `ʼ`
- Basic punctuation: `. , ! ? : ;`
- Ellipsis `…`
- Dashes: `—`, `–`, hyphen `-`
- Quotes: `"`, `„`, `"`, `"`, `«`, `»`
- Parentheses `( )` (for legitimate asides like `Я думав (мовчки)`)
- Whitespace

**Anything else** — Latin letters, digits, `|`, `/`, `\`, `<>`, `[]`, `{}`, `=`, `+`, emoji, arrows `→` / `->` — automatically disqualifies the line.

### Additional behavioural rules

The allowlist cannot spot Cyrillic-only garbage. Three extra checks:

1. **At least 1 Cyrillic letter.** A line like `).` or `,.` with pure punctuation is not poetry.
2. **ALL-CAPS stress marker.** Lowercase → uppercase within one token (`КрО`, `рЕж`, `тІ`) = scansion notation.
3. **Two or more intra-word hyphens between Cyrillic.** `за-гу-бив-ся` is syllable splitting, not a word.
4. **Bullet prefix.** `*`, `#`, `//`, or `- ` (with space) at line start. The em-dash `— ` is **allowed** — it opens dialogue.

### Salvage pass before verdict

Before dropping a line, the sanitizer **salvages** text in common cases:

- A parenthesized chunk with scansion content is stripped: `Темрява хутає місто, (Те-мря-ва ху-та-є)` → `Темрява хутає місто,`.
- Duplicated punctuation left after the strip is collapsed: `клас. (scansion).` → `клас..` → `клас.`.
- Legitimate parens are preserved: `Я думав (мовчки, тихо) про зорю` stays unchanged (Cyrillic + punctuation inside the parens — not scansion).

A paren is "scansion-flavoured" if its content contains a digit, Latin letter, arrow (`->`, `=>`), lower→upper Cyrillic, or an intra-word hyphen.

### Two-threshold minimum Cyrillic letters

In [`Poem.from_text`](../../src/domain/models/aggregates.py) there is a second line-level guard:

- A line ending with `. , ! ? ; : …` — a **finished utterance** → minimum **2** Cyrillic letters.
- A line without terminating punctuation — requires **5** (to weed out scansion stubs like `КО`, `жен`, `шу`).

This lets legitimate **short meters** (iambic monometer, scenario C05) survive: `У сні.` has 4 letters + a period → passes. `жен` without a period → drops.

## What if the sanitizer drops EVERYTHING

It returns an **empty string**. [`SanitizingLLMProvider`](../../src/infrastructure/llm/decorators/sanitizing_provider.py) sees the empty output and raises `LLMError`. That's the signal for the retry decorator to try once more. Exhausted retries fail the pipeline with *"LLM produced no valid poem lines after sanitization (response was pure reasoning/scansion)"*.

**Why not "fall back to the original text just in case"** — because that poisons the validator: it gets garbage, reports something (usually 0% and three violations), and the user sees an incoherent response. A clean failure is far better.

## Idempotence

Both stages are idempotent: `extract(extract(x)) == extract(x)` and `sanitize(sanitize(x)) == sanitize(x)`. After the first pass the text contains no `<POEM>` envelope and no characters outside the allowlist, so the second pass has nothing to do. This matters because retried generation attempts re-enter the same decorator chain, and the regeneration prompt feeds the previous (already-sanitized) poem back to the model — running cleaning twice on edge cases must not corrupt valid output.

## Envelope contract with the prompt

The `<POEM>...</POEM>` envelope is a contract negotiated with the model in the prompt. Both [`RagPromptBuilder`](../../src/infrastructure/prompts/rag_prompt_builder.py) and [`NumberedLinesRegenerationPromptBuilder`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) emit explicit `OUTPUT ENVELOPE (mandatory)` blocks instructing the model to wrap the final answer in the tags. `GeminiProvider` additionally repeats the rule in its `system_instruction` because Gemini gives system prompts higher priority. See [prompt_construction.md](./prompt_construction.md) for the full prompt shape.

## Tracing

Extractor + sanitizer write to [`ILLMCallRecorder`](../../src/domain/ports/llm_trace.py) on every call. The production adapter is [`InMemoryLLMCallRecorder`](../../src/infrastructure/tracing/llm_call_recorder.py) — it stores the most recent call's:

- `raw` — the raw model output (pre-extraction), written by `ExtractingLLMProvider` before extraction
- `extracted` — text after `<POEM>` envelope stripping, written by `ExtractingLLMProvider` after extraction
- `sanitized` — text after allowlist + salvage, written by `SanitizingLLMProvider` (recorded **even when empty**, so the trace clearly shows "sanitizer dropped everything" instead of leaving callers guessing)
- token usage (`input_tokens` / `output_tokens`), pushed by `GeminiProvider._record_usage`

`record_raw` resets `extracted` / `sanitized` to `""` so a stale value from a previous call cannot surface if those stages get skipped on a later one. The snapshot is read by [`ValidationStage`](../../src/infrastructure/stages/validation_stage.py) (iteration 0) and [`ValidatingFeedbackIterator`](../../src/infrastructure/regeneration/feedback_iterator.py) (iterations 1+) and stored in `IterationRecord.raw_llm_response` / `.sanitized_llm_response`. The UI renders it under "LLM trace (raw / sanitized)" on the generation and evaluation pages so a developer can see exactly what the model emitted vs. what the validator received.

## Extending it

Add a new drop rule → new regex + check in [`_is_garbage`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py). Add a salvage case → extend [`_paren_is_scansion`](../../src/infrastructure/sanitization/regex_poem_output_sanitizer.py).

**Always** add a unit test with the concrete garbage sample under [`tests/unit/infrastructure/sanitization/`](../../tests/unit/infrastructure/sanitization/) — this layer is most vulnerable to regressions (the model keeps inventing new leakage formats).

## See also

- [llm_decorator_stack.md](./llm_decorator_stack.md) — where the sanitizer sits in the stack and how it's invoked.
- [feedback_loop.md](./feedback_loop.md) — how invalid output flows into the feedback cycle.
