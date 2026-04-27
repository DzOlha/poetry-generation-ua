# Evaluation harness (research layer)

> The automated engine for **quantitatively measuring** system quality. 18 scenarios × 8 ablation configs = 144 runs per matrix pass. Results are aggregated into comparison tables for reporting; the batch runner extends the matrix with multiple seeds per cell and writes a flat CSV for downstream contribution analysis.

## Purpose

When a component is swapped (a different metric validator, a new sanitizer, another semantic retriever), we need to know: **is this objectively better**? Not "feels better", but "average meter accuracy across 18 test scenarios rose from 0.76 to 0.81".

This is standard research practice — an **ablation study**: fix the system, disable one component, measure the quality drop.

## Scenarios (18 of them)

Domain types live in [`src/domain/scenarios.py`](../../src/domain/scenarios.py) (`EvaluationScenario`, `ScenarioRegistry`). The concrete N01–N05, E01–E05, C01–C08 instances are application-level test data in [`src/infrastructure/evaluation/scenario_data.py`](../../src/infrastructure/evaluation/scenario_data.py).

Each scenario carries an `expected_to_succeed: bool` flag (default `True`). Two corner cases — **C04** (unsupported meter "гекзаметр") and **C08** (`foot_count=0`) — are marked `expected_to_succeed=False`. They intentionally crash `MeterSpec.__post_init__` with `UnsupportedConfigError`; `EvaluationService.run_scenario` catches this and records the trace as an aborted run instead of letting it explode the matrix. The batch runner can drop these up front via `--skip-degenerate` (see below).

### Normal (N01–N05) — typical cases

| ID | Theme | Meter / feet / rhyme |
|----|-------|----------------------|
| N01 | Spring in a forest | iamb, 4, ABAB |
| N02 | Love and separation | trochee, 4, AABB |
| N03 | Native land, Ukraine | dactyl, 4, ABBA |
| N04 | Loneliness | amphibrach, 4, ABAB (2 stanzas) |
| N05 | City at night | anapest, 4, AABB (2 stanzas) |

The "comfort zone": popular metres, moderate length, typical themes.

### Edge (E01–E05) — boundary cases

| ID | What it stresses |
|----|------------------|
| E01 | 2-foot iamb — very short lines |
| E02 | 6-foot iamb (alexandrine) — very long lines |
| E03 | 6-foot anapest with ABBA — rare meter+scheme combination |
| E04 | monorhyme AAAA — all four lines must rhyme (amphibrach 5) |
| E05 | abstract theme "time as an infinite spiral" (dactyl 5) |

Edge scenarios test boundary modes: very short/long, rare, abstract.

### Corner (C01–C08) — hard or broken cases

| ID | Scenario | `expected_to_succeed` |
|----|----------|-----------------------|
| C01 | minimal one-word theme "тиша" | True |
| C02 | very long multi-sentence theme (>200 chars) | True |
| C03 | theme in English (Latin script) | True |
| C04 | unsupported meter "гекзаметр" | **False** |
| C05 | 1-foot anapest — extreme minimal | True |
| C06 | special characters / HTML / emoji in theme — XSS-guard | True |
| C07 | mixed Ukrainian/Russian theme | True |
| C08 | `foot_count=0` — degenerate input | **False** |

Corner tests are **stress tests**: how does the system behave when the user does something strange?

## Ablation configs (A–H)

File: [`src/domain/evaluation.py`](../../src/domain/evaluation.py) — see `ABLATION_CONFIGS` and the `STAGE_*` constants. Each `AblationConfig.enabled_stages` is a frozen set of canonical stage names; `IStageSkipPolicy` consults `AblationConfig.is_enabled(stage.name)` to decide whether a togglable stage should run.

Mandatory stages always run regardless of config: `prompt_construction`, `initial_generation`, `final_metrics`. Togglable stages: `retrieval`, `metric_examples`, `validation`, `feedback_loop`.

| Config | Enabled togglable stages | Meaning |
|--------|--------------------------|---------|
| **A** | { validation } | Baseline: LLM writes the poem alone, we just validate, no corrections. No RAG, no metric examples, no feedback. |
| **B** | { validation, feedback_loop } | A + correction loop. No RAG, no metric examples. |
| **C** | { retrieval, validation, feedback_loop } | B + thematic retrieval. No metric examples. |
| **D** | { metric_examples, validation, feedback_loop } | B + metric examples. No thematic retrieval. |
| **E** | { retrieval, metric_examples, validation, feedback_loop } | Full system. |
| **F** | { retrieval, validation } | C minus feedback. Pure RAG effect on first draft. |
| **G** | { metric_examples, validation } | D minus feedback. Pure metric-examples effect. |
| **H** | { retrieval, metric_examples, validation } | E minus feedback. Pure combined enrichment effect. |

**Why these configs:** to **isolate the contribution** of each optional component, both with and without the feedback loop (because feedback masks the raw effect of enrichments — it iteratively repairs poor initial drafts and converges all arms to similar final quality).

With feedback (final-quality comparisons):
- **A → B**: how much does the feedback loop help?
- **B → C**: how much does semantic RAG add on top of feedback?
- **B → D**: how much do metric examples add on top of feedback?
- **D → E**, **C → E**: orthogonality of the two RAG mechanisms.

Without feedback (raw first-draft effect):
- **A → F**: pure semantic RAG, not muddled by feedback repair.
- **A → G**: pure metric-examples effect — the key metric for testing the "metric examples reduce iterations" hypothesis.
- **A → H**: pure combined effect of both enrichments.
- **H → E**: marginal value of feedback when the prompt is already enriched.

`DEFAULT_GENERATION_CONFIG` (label `"generate"`, all togglable stages enabled) is what the interactive `/generate` flow uses.

## Pipeline matrix

[`EvaluationService.run_matrix`](../../src/services/evaluation_service.py) iterates `scenarios × configs`, calling `run_scenario` for each cell and converting the resulting `PipelineTrace` into an `EvaluationSummary`. Total: 18 × 8 = **144 runs** per pass; `max_iterations=1` by default.

Each run produces one immutable `PipelineTrace` snapshot (stages, iterations, final poem, final metrics, total duration, error) and one `EvaluationSummary` row.

### Clock injection

`EvaluationService.run_scenario` receives an `IClock` and times the pipeline via `self._clock.now()` (start) and `self._clock.now() - t_global` (elapsed). The default adapter is `SystemClock`, which wraps `time.perf_counter`; tests inject a `FakeClock` to assert on duration without touching the wall clock. The port and `IDelayer` (see batch runner below) live in [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py).

## Final metrics

Each metric is a separate `IMetricCalculator` (`src/infrastructure/metrics/`) registered into a `DefaultMetricCalculatorRegistry` by [`CalculatorRegistrySubContainer.metric_registry`](../../src/infrastructure/composition/metrics_calculator_registry.py). `FinalMetricsStage` walks the registry, calls `calculate(EvaluationContext)` on each, and writes the dict into `PipelineTrace.final_metrics` (a calculator that throws is logged and stored as `0.0` — metrics never crash the run).

| Metric | What it answers |
|--------|-----------------|
| `meter_accuracy` | `valid_lines / total_lines` from the meter validator. Range `[0, 1]`. |
| `rhyme_accuracy` | `valid_pairs / total_pairs` from the rhyme validator. Range `[0, 1]`. |
| `regeneration_success` | Violation-coverage ratio between iteration 0 and the final iteration. `1 − final_violations / initial_violations` where violations = `(1 − meter) + (1 − rhyme)`. 1.0 = every violation fixed; 0.0 = none; negative = regeneration made things worse. Vacuous 1.0 if iteration 0 already had zero violations. |
| `semantic_relevance` | `cosine(embed(theme), embed(poem_text))`. Diagnostic — with the offline embedder this metric becomes noise. |
| `line_count` | `Poem.from_text(poem).line_count`. Diagnostic — should match `request.structure.total_lines`. |
| `meter_improvement` | `final − initial` meter accuracy across iterations. |
| `rhyme_improvement` | `final − initial` rhyme accuracy across iterations. |
| `feedback_iterations` | Number of feedback iterations performed (`len(iterations) − 1`, since iteration 0 is the initial validation). |
| `input_tokens` / `output_tokens` / `total_tokens` | Aggregated provider usage across every LLM call in the run. |
| `estimated_cost_usd` | Token totals × per-million tier prices from `AppConfig.gemini_input_price_per_m` / `gemini_output_price_per_m`. |

## Aggregation

[`DefaultEvaluationAggregator.aggregate(summaries, configs, scenarios)`](../../src/infrastructure/evaluation/aggregator.py) is pure computation — no I/O — and returns an `EvaluationAggregates(by_config, by_category)` value object.

### By config

For each `AblationConfig`, average meter / rhyme accuracy and iteration count across that config's runs, plus error count. Captured as `ConfigAggregate` rows. Differences between rows (E − A, C − B, D − B, etc.) quantify each component's contribution.

### By category

For each `ScenarioCategory` (Normal / Edge / Corner), average meter / rhyme accuracy and count errors across all runs in that category × every config. Captured as `CategoryAggregate` rows. Useful for spotting "system works on Normal, falls apart on Corner" plateaus.

`EvaluationRunner._log_aggregates` renders both into structured log lines.

## `make evaluate` flow

The Makefile recipe wraps [`scripts/run_evaluation.py`](../../scripts/run_evaluation.py) → [`EvaluationRunner`](../../src/runners/evaluation_runner.py). Variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SCENARIO` | Single scenario id (e.g. `N05`) | unset = all scenarios |
| `CONFIG` | Single ablation label (`A`–`E`) | unset = all configs |
| `CATEGORY` | `normal` / `edge` / `corner` | unset = all categories |
| `STANZAS` | Override stanza count | 2 |
| `LINES_PER_STANZA` | Override lines per stanza | 4 |
| `VERBOSE` | Emit per-trace detail | unset |
| `OUTPUT` | Output file path (JSON; Markdown twin written next to it) | `results/eval_<TS>.json` |

Examples:

```bash
make evaluate                            # all 18 × 8 = 144 runs
make evaluate SCENARIO=N05               # one scenario, all configs
make evaluate CATEGORY=normal CONFIG=C   # five normal scenarios, config C
```

The runner emits a summary table, by-config / by-category aggregate lines, and (when `OUTPUT` is set) a JSON trace file alongside a sibling Markdown report.

## `make ablation` flow (batch CSV)

[`BatchEvaluationRunner`](../../src/runners/batch_evaluation_runner.py) extends `EvaluationService` with seeds × configs × scenarios. Repeats every cell `SEEDS` times and streams one row per run through `IBatchResultsWriter` (the default `CsvBatchResultsWriter`) so partial progress is on disk if the process dies. Output: `<BATCH_DIR>/runs.csv` — one `BatchRunRow` per run.

The service constructor takes an `IDelayer`; `_iter_rows` calls `self._delayer.sleep(delay_between_calls_sec)` between LLM calls (skipped before the first executed call). The default `SystemDelayer` adapter wraps `time.sleep`; tests inject a `FakeDelayer` to verify throttling behaviour without sleeping.

| Variable | Purpose | Default |
|----------|---------|---------|
| `SEEDS` | Repetitions per (scenario, config) cell | 3 |
| `DELAY` | Seconds between LLM calls (rate-limit cushion) | 3 |
| `MAX_ITERATIONS` | Feedback iterations per run | 1 |
| `BATCH_DIR` | Output directory; `runs.csv` is written inside | `results/batch_<TS>` |
| `RESUME` | Read existing `runs.csv` and skip cells that already succeeded | unset |
| `SKIP_DEGENERATE` | Drop scenarios with `expected_to_succeed=False` (e.g. C04, C08) | unset |
| `SCENARIO` / `CONFIG` / `CATEGORY` | Same filters as `make evaluate` | unset |

Examples:

```bash
make ablation                                  # 18 × 8 × 3 = 432 runs
make ablation SEEDS=5 DELAY=5                  # more reps, kinder rate limit
make ablation SCENARIO=N01 CONFIG=E SEEDS=10   # variance check on one cell
make ablation SKIP_DEGENERATE=1                # skip C04 / C08 quota burners

# resume after a quota outage — same BATCH_DIR + RESUME=1
make ablation BATCH_DIR=results/batch_20260424_180000 RESUME=1
```

Resume semantics live in `BatchEvaluationRunner._load_resume_state`: existing rows with no `error` field are passed verbatim to `BatchEvaluationService.run` as `preserved_rows`, and their `(scenario_id, config_label, seed)` tuples populate `skip_cells`. The iterator silently passes those by; rows that died with an error get re-run.

`BatchRunRow` (in `src/domain/evaluation.py`) carries the same metrics as `EvaluationSummary` plus `regeneration_success`, `semantic_relevance`, `seed`, `category`, and `iteration_tokens` (a compact `it=<i>:in=<n>:out=<n>` per-iteration breakdown).

## Markdown report assembly

`MarkdownReporter` is now a thin façade over four collaborators in [`src/infrastructure/reporting/`](../../src/infrastructure/reporting/):

- [`TableFormatter`](../../src/infrastructure/reporting/table_formatter.py) — summary table layout with truncation widths.
- [`TraceFormatter`](../../src/infrastructure/reporting/trace_formatter.py) — per-trace plain-text block (stages, iteration history, intermediate poems, final poem, tokens & cost).
- [`CostCalculator`](../../src/infrastructure/reporting/cost_calculator.py) — pure USD pricing helper given per-million tier prices.
- [`MarkdownDocumentBuilder`](../../src/infrastructure/reporting/markdown_document_builder.py) — top-level section ordering: Generation Model → Config Legend → Summary → Aggregate by Config → Tokens & Cost → Trace Details.

The reporter wires them together via [`ReportingSubContainer.reporter`](../../src/infrastructure/composition/metrics_reporting.py); pricing comes from `AppConfig`. `JsonResultsWriter` (the default `IResultsWriter`) takes a reporter so the JSON write also drops a sibling `.md`.

## Composition layout

The metrics container was split into two focused sub-containers; `MetricsSubContainer` is now a façade preserving the public API:

- [`metrics_calculator_registry.py`](../../src/infrastructure/composition/metrics_calculator_registry.py) — registry, every `IMetricCalculator`, the `FinalMetricsStage`, and `DefaultStageRecordBuilder`.
- [`metrics_reporting.py`](../../src/infrastructure/composition/metrics_reporting.py) — `MarkdownReporter`, `JsonResultsWriter`, `CsvBatchResultsWriter`, `PipelineTracerFactory`, `DefaultHttpErrorMapper`, `DefaultEvaluationAggregator`.

Adding a metric touches only the calculator registry; tweaking the report touches only the reporting sub-container.

## Output files

Results export in two formats simultaneously when `OUTPUT` is set:

1. **JSON** — full `PipelineTrace` (stages, iterations, metrics) for each run, written by `JsonResultsWriter`. Designed for programmatic analysis.
2. **Markdown** — comparison tables + per-run detail blocks built by `MarkdownReporter`. Designed for reading / inclusion in a report.

Path: `results/eval_YYYYMMDD_HHMMSS.{json,md}`. Batch output: `<BATCH_DIR>/runs.csv`.

## Test coverage

- [`tests/unit/runners/test_batch_evaluation_runner.py`](../../tests/unit/runners/test_batch_evaluation_runner.py) — drives `BatchEvaluationRunner` against a hand-written fake `BatchEvaluationService` and a stub `IScenarioRegistry`. Covers arg validation, scenario / config filtering, resume on / off, missing-file resume, `skip_degenerate`, and kwarg pass-through. Pairs with the existing `test_runners.py` coverage of the generate / evaluate runners.

## Running

### Web UI

The `/evaluate` page picks one (scenario, config) cell and runs a single visualised trace. Not for the full matrix — for point diagnostics.

### API

`POST /api/evaluate` with body `{"scenario_id": "N05", "config_label": "E"}`. Synchronous — returns a JSON trace.

The matrix and batch runs are CLI-only.

## Key files

- [`src/services/evaluation_service.py`](../../src/services/evaluation_service.py) — `EvaluationService.run_scenario`, `run_matrix`
- [`src/services/batch_evaluation_service.py`](../../src/services/batch_evaluation_service.py) — `BatchEvaluationService`
- [`src/runners/evaluation_runner.py`](../../src/runners/evaluation_runner.py) — `make evaluate` entrypoint
- [`src/runners/batch_evaluation_runner.py`](../../src/runners/batch_evaluation_runner.py) — `make ablation` entrypoint
- [`src/domain/scenarios.py`](../../src/domain/scenarios.py) — `EvaluationScenario`, `ScenarioRegistry`
- [`src/infrastructure/evaluation/scenario_data.py`](../../src/infrastructure/evaluation/scenario_data.py) — N01–N05, E01–E05, C01–C08 instances
- [`src/domain/evaluation.py`](../../src/domain/evaluation.py) — `AblationConfig`, `ABLATION_CONFIGS`, `PipelineTrace`, `IterationRecord`, `StageRecord`, `EvaluationSummary`, `BatchRunRow`
- [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py) — `IClock`, `IDelayer`
- [`src/infrastructure/evaluation/aggregator.py`](../../src/infrastructure/evaluation/aggregator.py) — `DefaultEvaluationAggregator`
- [`src/infrastructure/metrics/`](../../src/infrastructure/metrics/) — every `IMetricCalculator` + `DefaultMetricCalculatorRegistry`
- [`src/infrastructure/reporting/`](../../src/infrastructure/reporting/) — `MarkdownReporter` façade + `TableFormatter` / `TraceFormatter` / `CostCalculator` / `MarkdownDocumentBuilder`
- [`src/infrastructure/composition/metrics_calculator_registry.py`](../../src/infrastructure/composition/metrics_calculator_registry.py) — calculator wiring
- [`src/infrastructure/composition/metrics_reporting.py`](../../src/infrastructure/composition/metrics_reporting.py) — reporting wiring

## Defaults

| Parameter | Value |
|-----------|-------|
| Scenario count | 18 (5 Normal + 5 Edge + 8 Corner) |
| Config count | 8 (A–H; E is the recommended default) |
| Default feedback iterations | 1 |
| Default seeds (batch) | 3 |
| Default delay between LLM calls (batch) | 3 s |
| Retrieval top-k | 5 (search) / 2 (into prompt) |
| Metric examples top-k | 2 |
| Stanzas × lines per stanza (CLI) | 2 × 4 |

## Caveats

- **Reproducibility.** Gemini is not deterministic — even with `temperature=0`, responses differ between runs. For rigorous experiments use `make ablation SEEDS=5` and average.
- **Offline mode.** With `OFFLINE_EMBEDDER=true` the `semantic_relevance` metric becomes noise. Other metrics stay valid.
- **Corner scenarios skew averages.** If you want one number to compare configs, exclude corner from the average. The by-category aggregate puts them on a separate row precisely for this.
- **Time budget.** The full matrix takes ≈ 30–60 min with a real provider; the full batch (×3 seeds) is ≈ 1.5–3×. The web UI only supports single runs.
- **Iteration counts.** `max_iterations=1` is the minimum for comparison. More gives better quality in E but run time grows linearly.

## See also

- [`system_overview.md`](./system_overview.md) — high-level system tour.
- [`feedback_loop.md`](./feedback_loop.md) — what is disabled in configs A and D.
- [`semantic_retrieval.md`](./semantic_retrieval.md) — what is disabled in configs A, B, D.
- [`meter_validation.md`](./meter_validation.md), [`rhyme_validation.md`](./rhyme_validation.md) — metric formulas.
