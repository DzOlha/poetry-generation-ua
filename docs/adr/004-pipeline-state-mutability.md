# ADR-004: Mutable PipelineState in the Domain Layer

## Status
Accepted

## Context
The poem-generation pipeline runs an ordered chain of stages
(`RetrievalStage` → `MetricExamplesStage` → `PromptStage` →
`GenerationStage` → `ValidationStage` → `FeedbackLoopStage`). Each stage
needs to read what previous stages produced and to publish its own
output for downstream consumers — retrieved excerpts, metric examples,
the constructed prompt, the raw poem text, validation results, and
iteration history.

The rest of the domain layer is built on frozen, immutable value
objects (`MeterSpec`, `RhymeScheme`, `GenerationRequest`, `MeterResult`,
`RhymeResult`, `LineFeedback`, `PairFeedback`, `PipelineTrace`,
`EvaluationSummary`, etc.). The audit flagged that `PipelineState` —
also a domain dataclass — is the lone exception: it is not frozen, and
stages mutate its fields in place.

Two alternatives were considered:

1. **Per-stage state copies.** Each stage takes the current state and
   returns a new one with its slice updated (`replace(state, poem=...)`).
   Stage signatures become `IPipelineStage.run(state) -> PipelineState`
   instead of `IPipelineStage.run(state) -> None`.

2. **Shared mutable accumulator.** The current design: stages write
   their outputs directly onto the shared state object the pipeline
   threads through them.

Option 1 is more "pure" but multiplies allocation and boilerplate. The
state has ~12 fields and seven stages mutate it; each stage's `replace`
call would copy the other eleven. More importantly, the pipeline is the
*only* consumer of `PipelineState` — no service or handler reads it
after the run finishes (they read the `PipelineTrace` snapshot the
tracer builds, which IS frozen). So the mutability is contained to a
single module's lifecycle.

## Decision
`PipelineState` stays mutable. The deviation from the otherwise-frozen
domain is intentional and confined to the pipeline lifecycle:

- `PipelineState` is constructed at the start of `EvaluationService.run_scenario`
  / `PoetryService.generate` and discarded the moment the pipeline returns.
- Only `IPipelineStage.run` implementations are allowed to mutate it.
- The post-pipeline snapshot every caller reads (`PipelineTrace`) is
  built by the tracer and is a frozen value object, so observable state
  outside the pipeline is still immutable.

## Consequences
- Stage authors must remember that the state object they receive is
  shared. Mutations are not isolated; ordering matters. This is the
  cost of the trade-off and is mitigated by the small number of stages
  and the fact that each stage owns a disjoint slice of fields.
- Tests that exercise individual stages can construct a `PipelineState`
  cheaply; they do not need to thread an immutable copy through.
- If a future stage needs to *read* a value another stage has not yet
  written, the absence is detectable (the field is `None`) and tests
  catch it before runtime.
- New domain models continue to be frozen by default. `PipelineState`
  is the documented exception, not a precedent.

## References
- `src/domain/pipeline_context.py` — the `PipelineState` definition.
- `src/infrastructure/pipeline/sequential_pipeline.py` — the threading
  contract.
- ADR-001 (Hexagonal Architecture) — the broader immutability discipline.
