# Feedback loop

> The iterative-correction algorithm: how the pipeline turns validator feedback into a regeneration prompt, splices the fixed lines back into the previous version, decides when to stop, and surfaces per-iteration debug data.

## Overview

After initial generation + validation the system holds a set of structured violations: `LineFeedback` for meter problems and `PairFeedback` for rhyme problems. Instead of dropping the poem, the loop runs:

```
iteration N (N ≥ 1):
  1. if stop_policy says "stop" → break
  2. take the current poem (prev_poem) and the previous feedback
  3. ask the LLM to fix it (regenerate_lines OR full regeneration)
  4. merge the new lines into prev_poem
  5. re-validate the merged poem → new feedback
  6. record an IterationRecord in the trace (with LLM snapshots)
```

The goal is **targeted correction**: don't re-run the whole poem, only replace the lines that carry violations. This saves tokens and usually preserves semantics.

## Pipeline structure

The feedback loop is the last togglable stage in the generation pipeline:

```
FeedbackLoopStage  (skips when ablation config disables it OR validation
        │           was skipped)
        ▼
ValidatingFeedbackIterator   (orchestrates the iteration loop)
        │
        ├── IFeedbackCycle           — ValidationFeedbackCycle
        │     ├── IMeterValidator
        │     ├── IRhymeValidator
        │     └── IFeedbackFormatter — UkrainianFeedbackFormatter
        │
        ├── IRegenerationMerger      — LineIndexMerger
        │
        ├── IIterationStopPolicy     — MaxIterationsOrValidStopPolicy
        │
        ├── ILLMProvider             — full decorator stack
        │
        └── ILLMCallRecorder         — captures raw / extracted /
                                       sanitized response per iteration
```

| Class / file | Role |
|--------------|------|
| [`FeedbackLoopStage`](../../src/infrastructure/stages/feedback_stage.py) | Pipeline-stage façade. Honours the ablation skip policy and writes a closing `StageRecord` summarising the loop. |
| [`ValidatingFeedbackIterator`](../../src/infrastructure/regeneration/feedback_iterator.py) | Top-level orchestrator. Iterates `range(1, max_iterations + 1)`, catches `DomainError`, writes one `IterationRecord` per iteration. |
| [`ValidationFeedbackCycle`](../../src/infrastructure/regeneration/feedback_cycle.py) | Bundles meter/rhyme validators + the feedback formatter into one `.run()` → `FeedbackCycleOutcome`. |
| [`LineIndexMerger`](../../src/infrastructure/regeneration/line_index_merger.py) | Splices regenerated lines back into the previous poem via the structured violation indices. |
| [`MaxIterationsOrValidStopPolicy`](../../src/infrastructure/regeneration/iteration_stop_policy.py) | Stop rule: poem is valid OR iteration limit reached. |
| [`NumberedLinesRegenerationPromptBuilder`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) | Builds the regeneration prompt with numbered lines + a bullet list of violations. |
| [`UkrainianFeedbackFormatter`](../../src/infrastructure/feedback/ukrainian_formatter.py) | Renders `LineFeedback` / `PairFeedback` into the natural-language strings the LLM sees. |

## Per-iteration algorithm

See [`feedback_iterator.py`](../../src/infrastructure/regeneration/feedback_iterator.py); annotations below.

### Step 1: stop-policy check

`MaxIterationsOrValidStopPolicy.should_stop(iteration, max_iterations, meter_result, rhyme_result, history)` returns `True` when:
- `iteration > max_iterations`, **OR**
- `meter_result.ok and rhyme_result.ok` (poem is already valid — no point continuing).

Adding a new policy (e.g. "stop after N consecutive non-improving regens") = implement `IIterationStopPolicy` and wire it in via the composition root.

### Step 2: regeneration strategy

The iterator inspects the **current line count** in the poem. If it does not match `request.structure.total_lines` (e.g. the sanitizer dropped a chain-of-thought leak and 4 → 3), it runs a **full regeneration** through `llm.generate(state.prompt)` with the original prompt — line-by-line regen cannot reconstruct a missing line.

Otherwise the iterator runs a **partial regeneration** via `llm.regenerate_lines(state.poem, feedback_messages)`.

### Step 3: decorator stack pass-through

`llm.generate` / `llm.regenerate_lines` traverse the full [decorator stack](./llm_decorator_stack.md): logging → retry → timeout → sanitizing → extracting → Gemini. After the call, `llm_snapshot = self._llm_recorder.snapshot()` captures `raw` / `extracted` / `sanitized` text plus token usage for the trace.

### Step 4: cleanup and sanity check

```python
regenerated = Poem.from_text(raw).as_text()
if not regenerated:
    state.poem = prev_poem        # all garbage — keep previous
```

`Poem.from_text` filters again (see [sanitization_pipeline.md](./sanitization_pipeline.md)). If nothing survives — the poem is not updated. The next validation surfaces the same violations, the iteration counter advances, and the stop policy will eventually break the loop.

### Step 5: merging via `LineIndexMerger`

This is the interesting part. [`LineIndexMerger.merge()`](../../src/infrastructure/regeneration/line_index_merger.py) has three branches:

**Case A — full poem.** If `regenerated` has exactly as many lines as `original` → return `regenerated` as-is. The model fixed everything itself.

**Case B — partial splice.** If `regenerated` is shorter:
1. Collect violation indices from `LineFeedback.line_idx` and `PairFeedback.line_b_idx` (the rhyme merger always rewrites the **B** line of a pair).
2. Walk the sorted indices and splice each regenerated line into `original` at the corresponding violation position.

If the merger has no usable violation indices, or fewer regenerated lines than violations to fill, it returns `regenerated` unchanged.

**Case C — safety fallback.** If every line in `regenerated` is a verbatim copy of an existing `original` line, the LLM dropped the violating line(s) instead of rewriting them. Splicing those clean lines into the violation slots would silently destroy the rhyme pair. Return `original` unchanged.

After the special "full regeneration" branch (Step 2), no merging happens — the iterator simply overwrites `state.poem = regenerated`, because the original poem is already corrupted and not safe to splice into.

### Step 6: re-validation + iteration record

The merged poem goes through `ValidationFeedbackCycle.run()` → fresh `m_result`, `r_result`, `feedback_messages`. An `IterationRecord` is appended to the trace:

```python
IterationRecord(
    iteration=it,
    poem_text=state.poem,
    meter_accuracy=m_result.accuracy,
    rhyme_accuracy=r_result.accuracy,
    feedback=feedback_messages,
    duration_sec=t_iter.elapsed,
    raw_llm_response=llm_snapshot.raw,
    sanitized_llm_response=llm_snapshot.sanitized,
    input_tokens=llm_snapshot.input_tokens,
    output_tokens=llm_snapshot.output_tokens,
)
```

The trace fields (`raw_llm_response`, `sanitized_llm_response`, `input_tokens`, `output_tokens`) feed the `/evaluate` UI debug view and the Markdown report's per-iteration tokens-and-cost line.

## Structured feedback objects

`LineFeedback` and `PairFeedback` live at [`src/domain/models/feedback.py`](../../src/domain/models/feedback.py) (they were moved here from the old `src/domain/feedback.py` location).

- **`LineFeedback`** — meter violation for a single line. Fields: `line_idx`, `meter_name`, `foot_count`, `expected_stresses`, `actual_stresses`, `total_syllables`, `expected_syllables`, `extra_note`.
- **`PairFeedback`** — rhyme violation between two lines. Fields: `line_a_idx`, `line_b_idx`, `scheme_pattern`, `word_a`, `word_b`, `rhyme_part_a`, `rhyme_part_b`, `score`, `clausula_a`, `clausula_b`, `precision`.

These are dataclasses used by both the merger (which reads `line_idx` / `line_b_idx`) and the formatter (which renders them as natural-language strings). The merger does **not** parse the formatter's output — it consumes the structured objects directly, so the prompt-string format can change without breaking merging.

`format_all_feedback(formatter, line_fbs, pair_fbs)` is a small helper that renders meter feedback first then rhyme feedback through any object satisfying the `_FeedbackFormatterProto` structural type.

### `UkrainianFeedbackFormatter`

`IFeedbackFormatter` is implemented by [`UkrainianFeedbackFormatter`](../../src/infrastructure/feedback/ukrainian_formatter.py), which renders the LLM-facing strings:

- `format_line(LineFeedback)` → `"Line N violates <meter>... Expected stress on syllables: ... Actual stress on syllables: ... Rewrite only this line, keep the meaning."` (1-based line numbers, optional syllable shorten/lengthen note).
- `format_pair(PairFeedback)` → `"Lines A and B should rhyme (scheme XYZW). Expected rhyme with ending '...'. Current ending '...' does not match (score: 0.45). Rewrite line B keeping the meaning and meter."` (with optional clausula and precision notes).

## Regeneration prompt format

[`NumberedLinesRegenerationPromptBuilder`](../../src/infrastructure/prompts/regeneration_prompt_builder.py) produces something like:

```
You are given a Ukrainian poem with line numbers and a list of violations.
Fix ONLY the lines mentioned in the feedback. Copy all other lines exactly unchanged.
Return the COMPLETE poem — every line, in the correct order — with no line numbers, no commentary, no markdown.

OUTPUT ENVELOPE (mandatory):
Wrap your FINAL corrected poem between the literal tags <POEM> and </POEM>. ...

POEM (with line numbers for reference):
1: Спинися, мить, на цім порозі,
2: Де тихо світяться вогні.
3: Замри на зоряній дорозі,
4: Навій чарівний сон мені.

VIOLATIONS TO FIX:
- Line 1 violates ямб meter ...
- Line 3 violates ямб meter ...
```

The model is asked to return the **full poem** (every line in order) but rewrite **only the flagged ones**. The merger then handles the response: Case A if it kept the line count, Case B if it returned just the fixed lines.

The prompt **mandates** wrapping the poem in a `<POEM>…</POEM>` envelope (see [sanitization_pipeline.md](./sanitization_pipeline.md)) and forbids hyphenated syllables, all-caps tokens, scansion notation, bare digits, English commentary, etc.

## `RegenerationSuccessCalculator` metric

The success of the feedback loop is measured by [`RegenerationSuccessCalculator`](../../src/infrastructure/metrics/regeneration_success.py) (registered into the metric registry as `regeneration_success`). It computes:

```
violations(it) = (1 − meter_accuracy(it)) + (1 − rhyme_accuracy(it))
score = 1 − final_violations / initial_violations   (0 if fewer than 2 iterations)
```

So `1.0` = every initial violation fixed, `0.0` = none fixed, negative = the loop made things worse. If the poem already had zero violations at iteration 0, the metric is vacuously `1.0`. This violation-coverage form is preferred over a raw accuracy delta because a metric already at the ceiling (e.g. rhyme = 100%) cannot improve and unfairly drags a delta-based mean down.

## Defensive invariants

- **Abort on `DomainError`.** Any error inside the loop body (`LLMError`, `ValidationError`, …) → record `StageRecord(name=f"feedback_iter_{it}", error=...)` and `break`. The pipeline survives, the run does not crash.
- **No empty overwrites.** If the sanitizer returned empty — keep `prev_poem`.
- **Never lose lines.** The merger rules guarantee `state.poem` line count cannot decrease.
- **Iteration 0 is created elsewhere.** [`ValidationStage`](../../src/infrastructure/stages/validation_stage.py) writes the `IterationRecord(iteration=0, …)` after initial validation; the iterator only writes records for `iteration >= 1`.

## Configuration

- **`max_iterations`** on `GenerationRequest`: effective iteration cap. The web form clamps it to `[0, 3]`. `0` = no feedback loop at all (just initial generation + validation).
- **Ablation toggle:** `feedback_loop` is a togglable stage. Configs `A` keep it off; configs `B`, `C`, `D`, `E` keep it on.
- **`LLM_TIMEOUT_SEC` / `LLM_RETRY_MAX_ATTEMPTS`** — every `llm.regenerate_lines` call goes through the decorator stack. See [reliability_and_config.md](./reliability_and_config.md).
- **`iteration_stop_policy`** — swap for a custom `IIterationStopPolicy` in the composition root.

## Gotchas

- **Iteration 0 ≠ regeneration.** Iteration 0 records the initial generation + first validation; it is created by `ValidationStage`, not by the iterator.
- **Full regeneration on length mismatch is a separate branch.** It runs *before* the merger and overwrites `state.poem` directly — Cases A/B/C of the merger are not used in that branch.
- **`cached_feedback`** on `PipelineState` — `ValidationStage` formats the initial feedback once and stores it; the iterator reuses it for the first iteration's prompt instead of formatting twice.
- **Token snapshots.** Each `IterationRecord` carries `input_tokens` / `output_tokens` from the LLM call recorder. `0` means "not available" (mock adapter, safety block, SDK drift) — consumers must treat it as unknown, not free.

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Iteration 0 and 1 are identical garbage | Sanitizer let garbage through, merger Case A returned identical text | Add a rule to the sanitizer (see [sanitization_pipeline.md](./sanitization_pipeline.md)) |
| 3 lines instead of 4 in the final poem | `Poem.from_text` dropped a line under `_MIN_CYR_LETTERS` | Inspect rules in `src/domain/models/aggregates.py` |
| Iteration 1 makes things worse | Regeneration prompt received imprecise feedback | Check `UkrainianFeedbackFormatter` and the structured `LineFeedback` |
| Timeout on `regenerate_lines` → retry also times out | Reasoning model with `max_tokens` too low | Raise `GEMINI_MAX_TOKENS` or `LLM_TIMEOUT_SEC` |

## See also

- [`evaluation_harness.md`](./evaluation_harness.md) — how the loop fits into the ablation matrix and which configs disable it.
- [`llm_decorator_stack.md`](./llm_decorator_stack.md) — what every `llm.*` call passes through.
- [`sanitization_pipeline.md`](./sanitization_pipeline.md) — where the raw response is cleaned.
- [`reliability_and_config.md`](./reliability_and_config.md) — timeout, retry, tuning.
