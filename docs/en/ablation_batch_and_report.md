# Batch evaluation & ablation report (research layer)

> The full research pipeline that turns *"is component X actually useful?"* into a **statistically defensible answer**. Three stages: run the matrix → compute paired-Δ contributions → render a dashboard. Each stage is invoked separately so a quota outage in stage 1 does not lose stage-2 work.

This document picks up where [evaluation_harness.md](./evaluation_harness.md) leaves off. The harness is the *ablation engine* (one matrix pass = 18 scenarios × 5 configs = 90 runs). The **batch** flow on this page extends that engine with multiple seeds per cell, paired-Δ statistics across configs, and a dashboard that turns the raw numbers into a verdict.

## Three-stage pipeline at a glance

```
┌──────────────────────────────────────────────────────────┐
│ Stage 1:  make ablation       (scripts/run_batch_evaluation.py)
│           18 × 5 × seeds = N runs through the LLM
│           ───►  results/batch_<ts>/runs.csv
├──────────────────────────────────────────────────────────┤
│ Stage 2:  make ablation-report RUNS=<runs.csv>
│           (scripts/analyze_contributions.py)
│           paired-Δ + bootstrap CI + Wilcoxon p
│           ───►  contributions.csv
│           ───►  contributions_by_cat.csv
│           ───►  report.json   (metadata + cost summary)
│           ───►  plots/forest.png
│           ───►  plots/box_by_config.png
│           ───►  plots/heatmap.png
│           ───►  plots/contribution_by_cat.png
├──────────────────────────────────────────────────────────┤
│ Stage 3:  /ablation-report       (HTML dashboard)
│           GET /evaluation/ablation-report  (JSON twin)
│           ───►  glossary + plots + auto-narrative + insights
└──────────────────────────────────────────────────────────┘
```

The three stages share files via the filesystem (`results/batch_<ts>/`), not an in-memory pipeline. That is intentional: stage 1 is the expensive one (real LLM calls), and any artifact it has already produced survives a quota outage, a network blip, or even a process restart.

---

## Stage 1 — `make ablation`

Defined in [`Makefile:183-185`](../../Makefile#L183-L185) and [`scripts/run_batch_evaluation.py`](../../scripts/run_batch_evaluation.py); the heavy lifting lives in [`src/runners/batch_evaluation_runner.py`](../../src/runners/batch_evaluation_runner.py) and [`src/services/batch_evaluation_service.py`](../../src/services/batch_evaluation_service.py).

### What it does

For every triple `(scenario, ablation_config, seed)` it calls `EvaluationService.run_scenario(...)` and writes one row of `BatchRunRow` (see [`src/domain/evaluation.py:191`](../../src/domain/evaluation.py#L191)) into `runs.csv`. Rows are streamed to disk as soon as they finish — so a crash mid-batch leaves a partial CSV with all completed rows intact.

The seed dimension exists because LLM output is stochastic. With one seed per cell a single lucky/unlucky generation can dominate the verdict. With multiple seeds, paired-Δ statistics in Stage 2 can quantify how much of any observed difference is *real* component contribution vs *noise* from generation variance.

### CLI / Make variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SEEDS` | `3` | Repetitions per `(scenario, config)` cell. Total runs = `seeds × n_scenarios × n_configs`. |
| `SCENARIO` | *(all 18)* | Restrict to one scenario ID, e.g. `N01`. |
| `CONFIG` | *(all A–H)* | Restrict to one ablation config. **E** is the recommended default for the full system; A–D are intermediate with feedback; F–H are research-only without feedback. |
| `CATEGORY` | *(all)* | Filter by category: `normal`, `edge`, `corner`. |
| `DELAY` | `3` (sec) | Seconds the runner sleeps between LLM calls — breathing room for rate limits. Injected as `IDelayer.sleep`, so tests can run in zero real time. |
| `MAX_ITERATIONS` | `1` | Feedback regeneration cap per run. `0` = no feedback even if config B/C/D/E enables it. |
| `BATCH_DIR` | `results/batch_<ts>` | Folder receiving `runs.csv`. Use a fixed name when resuming. |
| `RESUME` | *(off)* | When `1`, read existing `runs.csv` and skip cells whose previous run succeeded. |
| `SKIP_DEGENERATE` | *(off)* | Drop scenarios with `expected_to_succeed=False` (C04 unsupported meter, C08 zero feet) before the matrix. They burn quota for nothing — Stage 2 already filters them anyway. |

### Resume semantics

The audit incident that motivated the resume flag was a 250-RPD Gemini quota cap kicking in mid-run on row 156 of 270. Without resume the entire batch had to restart at row 1, paying for already-completed rows again. With `RESUME=1`:

1. The runner reads existing `runs.csv` via `read_existing_runs(...)`.
2. Rows with a non-empty `error` column are dropped (we want to retry those).
3. Successful rows go into `preserved_rows` (passed verbatim to the writer first) and their cell keys go into `skip_cells`.
4. The iterator skips any `(scenario, config, seed)` triple in `skip_cells` — no LLM call, no token spent.
5. The final CSV is the union: preserved rows + freshly-run rows.

The contract is the responsibility of [`BatchEvaluationRunner._load_resume_state`](../../src/runners/batch_evaluation_runner.py#L122) and is exercised by [`tests/unit/runners/test_batch_evaluation_runner.py`](../../tests/unit/runners/test_batch_evaluation_runner.py) in `TestResume`.

### `runs.csv` format — one row per run

Columns map directly to `BatchRunRow`:

| Column | Type | Notes |
|--------|------|-------|
| `scenario_id` | str | `N01`–`N05`, `E01`–`E05`, `C01`–`C08` |
| `scenario_name` | str | Human-readable name |
| `category` | str | `normal` / `edge` / `corner` |
| `meter`, `foot_count`, `rhyme_scheme` | str/int/str | Echoed from the scenario for downstream filtering |
| `config_label` | str | `A`–`E` |
| `config_description` | str | Echoed from `AblationConfig.description` |
| `seed` | int | 0..seeds-1 |
| `meter_accuracy`, `rhyme_accuracy` | float | `[0, 1]` — the headline structural metrics |
| `regeneration_success` | float | Violation-coverage delta (see [feedback_loop.md](./feedback_loop.md)). Can be **negative**: feedback can hurt. |
| `semantic_relevance` | float | Cosine similarity between theme and final poem (LaBSE) |
| `num_iterations` | int | How many feedback iterations actually ran |
| `num_lines` | int | Generated poem length |
| `duration_sec` | float | Wall-clock for the whole run; produced from `IClock.now()` so tests can stub it |
| `input_tokens`, `output_tokens`, `total_tokens` | int | LLM usage totals across the run |
| `estimated_cost_usd` | float | `input_tokens × $/M_in + output_tokens × $/M_out` (computed by `EstimatedCostCalculator`) |
| `iteration_tokens` | str | Per-iteration breakdown serialised as `it=<idx>:in=<n>:out=<n>,…` so the CSV stays a flat row |
| `error` | str/empty | Set when the pipeline raised; Stage 2 drops these rows from the statistics |

### Time abstraction

`BatchEvaluationService.__init__` takes an `IDelayer`; `EvaluationService.run_scenario` takes an `IClock` (see [`src/domain/ports/clock.py`](../../src/domain/ports/clock.py)). Production wires `SystemDelayer` / `SystemClock`; tests inject `FakeDelayer` / `FakeClock` so unit tests for the runner finish in milliseconds while still exercising the throttling and timing paths. The audit's fix #2 covers this.

---

## Stage 2 — `make ablation-report`

Implemented in [`scripts/analyze_contributions.py`](../../scripts/analyze_contributions.py); driven by [`Makefile:198-204`](../../Makefile#L198).

### What it does

Reads `runs.csv`, computes **paired Δ statistics** for every (component, metric) pair, renders four matplotlib PNGs, and emits a `report.json` aggregate. Output lands next to the input CSV, so a `batch_<ts>/` folder ends up self-contained.

### Why paired Δ

Each row in `runs.csv` is one (scenario, config, seed) run. To measure *the effect of a component* we cannot simply compare averages — different scenarios have wildly different baseline difficulty, and noise from "this scenario is easier than that one" would swamp any real component effect.

The paired-Δ trick is:
- For each `(scenario_id, seed)` pair, take the metric value under config X and under config Y.
- Subtract: `Δ = X − Y` is the **same scenario under same seed**, only the toggled component differs.
- Average those Δ over all `(scenario_id, seed)` pairs and you have the component's mean effect with scenario difficulty *paired out*.

That is what `ContributionAnalyzer._compute` does: pivot on `(scenario_id, seed)` × `config_label`, then take column differences.

### Component definitions (the five comparisons)

```
feedback_loop          = B − A         (added on top of baseline)
semantic_rag           = C − B         (added on top of feedback)
metric_examples        = D − B         (added on top of feedback)
rag_metric_combined    = E − B         (both RAG variants together)
interaction_rag_metric = E − C − D + B (2-way interaction term)
```

The 2-way interaction tells you whether the two RAG variants are **synergistic, additive, or competing**:

- `Δ_interaction > 0` → synergy (combined > sum of parts)
- `Δ_interaction ≈ 0` → effects just add up
- `Δ_interaction < 0` → competition (one variant suppresses the other, e.g. they fight for prompt budget)

### Metrics analysed

`METRICS = ("meter_accuracy", "rhyme_accuracy", "regeneration_success", "semantic_relevance")`. The first two are the headline structural metrics; the other two surface the regeneration loop's effect and thematic alignment.

### Statistical significance

For each (component, metric) pair the analyzer reports:

- **`mean_delta`** — mean of the paired Δ vector.
- **`ci_low`, `ci_high`** — 95 % percentile **bootstrap confidence interval** on that mean. 10 000 resamples; seeded RNG (`RNG_SEED = 42`) so the report is reproducible.
- **`p_value`** — two-sided **Wilcoxon signed-rank** p-value. Non-parametric, robust to non-normal Δ distributions (LLM outputs are heavy-tailed). Returns 1.0 if the test is undefined (all Δ zero).
- **`significant`** — derived flag: **CI does not cross zero**. We use this rather than the p-value because at small *n* the bootstrap CI is the more honest signal; the p-value is reported for completeness but does not drive the dashboard's verdicts.

### `contributions.csv` columns

```
category, component, comparison, metric, n, mean_delta,
ci_low, ci_high, p_value, significant
```

`category` is `"overall"` for the top-level table; `contributions_by_cat.csv` uses the same schema with `category ∈ {"normal", "edge", "corner"}` for the per-category breakdown.

### `report.json`

A small JSON manifest that the dashboard consumes:

```json
{
  "batch_id": "batch_20260425_204756",
  "runs_csv": "results/batch_20260425_204756/runs.csv",
  "total_runs": 270,
  "error_runs": 4,
  "seeds": 3,
  "n_scenarios": 18,
  "n_configs": 5,
  "configs": ["A", "B", "C", "D", "E"],
  "metrics": ["meter_accuracy", "rhyme_accuracy",
              "regeneration_success", "semantic_relevance"],
  "components": ["feedback_loop", "semantic_rag", "metric_examples",
                 "rag_metric_combined", "interaction_rag_metric"],
  "plots": { "forest": "plots/forest.png", "box": "plots/box_by_config.png",
             "heatmap": "plots/heatmap.png", "by_category": "plots/contribution_by_cat.png" },
  "bootstrap_iterations": 10000,
  "ci_level": 95.0,
  "cost": { /* …token & cost aggregates per config… */ }
}
```

The cost block carries totals + per-config token/cost breakdowns (`_cost_summary` in the analyser). It is what the dashboard's "Sumарно витрачено $X на N токенів" line uses.

### The four plots

All rendered headless via `matplotlib.use("Agg")` so the script works in containers with no display.

| File | What it shows | How to read |
|------|---------------|-------------|
| `plots/forest.png` | One row per component, error-bar `[ci_low, ci_high]` around `mean_delta`. Four sub-plots, one per metric. | **Green** dot = significant positive. **Red** = significant negative. **Grey** = CI crosses zero (effect inconclusive). The vertical dashed line is `Δ = 0`. |
| `plots/box_by_config.png` | Boxplot of each metric over 8 configs A–H (no pairing). Median, quartiles, outliers, mean (blue diamond). | Tall box = noisy config. High median in E vs A = full system actually moves the needle on average. The E vs H contrast isolates the feedback loop's contribution. |
| `plots/heatmap.png` | `(config × scenario)` mean of each metric. | Green = high, red = low. For `regeneration_success` we use a diverging palette centred on zero because the metric is signed. Red columns = scenarios no config solves; red rows = bad configs. |
| `plots/contribution_by_cat.png` | Same paired-Δ + CI as the forest plot, but split by `normal` / `edge` / `corner` categories. | Common pattern: components are nearly neutral on `normal` but help noticeably on `edge` / `corner` — the baseline already saturates the easy cases, leaving "room to grow" only on harder ones. |

### Cost summary (`_cost_summary`)

Aggregates token usage across the whole batch and per config:

- `total_input_tokens`, `total_output_tokens`, `total_tokens`
- `total_cost_usd` (sum of `estimated_cost_usd` across successful rows)
- `avg_tokens_per_run`, `avg_cost_per_run_usd`
- `per_config[]` — same fields scoped to each config label

Returns zero-valued fields (not `null`) when the token columns are absent so template numeric formatters need no special-casing.

---

## Stage 3 — the dashboard

Two surfaces serve **the same payload**:

- **HTML**: `GET /ablation-report` (`src/handlers/web/routes/ablation_report.py`) renders [`ablation_report.html`](../../src/handlers/web/templates/ablation_report.html).
- **JSON**: `GET /evaluation/ablation-report` (`src/handlers/api/routers/evaluation.py`) returns `AblationReportResponseSchema` for SPAs.

Both call **the same builder**: [`build_artifacts(results_dir, registry)`](../../src/handlers/shared/ablation_report.py) in `src/handlers/shared/ablation_report.py`. The web route renders the result with Jinja; the API route reshapes it into Pydantic. **Returns `None` / 404 when no batch artifacts exist.**

### The `BatchArtifacts` payload

`BatchArtifacts` (in `src/handlers/shared/ablation_report.py`) is the canonical value object:

```python
@dataclass
class BatchArtifacts:
    batch_id: str                      # e.g. "batch_20260425_204756"
    metadata: dict                     # the contents of report.json
    contributions: list[dict]          # rows of contributions.csv
    contributions_by_cat: list[dict]   # rows of contributions_by_cat.csv
    plot_urls: dict[str, str]          # name → /results/<batch>/plots/*.png
    components: list[ComponentExplanation]   # static glossary
    plot_explanations: dict[str, PlotExplanation]   # static methodology captions
    plot_analyses: dict[str, PlotAnalysis]   # auto-generated per-batch narrative
    scenarios_by_category: list[dict]  # scenario catalogue grouped NORMAL/EDGE/CORNER
    configs: list[dict]                # ablation config catalogue with long descriptions
    insights: dict                     # headline + per-(component, metric) verdicts + cost
```

The first five blocks are static for a given batch (raw numbers + URLs to PNGs). The last six are the **meaning layer** — readable narrative that turns the numbers into something a human can quote in a conclusions section.

### Static narrative

Two static tables travel with the dashboard:

- **`COMPONENT_GLOSSARY`** — for every component (feedback_loop, semantic_rag, metric_examples, rag_metric_combined, interaction_rag_metric): a label, the comparison formula (`B − A`, etc.), a "what does enabling this do" summary, and an interpretation guide for what the Δ means.
- **`PLOT_GLOSSARY`** — for every plot (forest, box, heatmap, by_category): a title, a "what is plotted" caption, a "how to read" guide, and a "what to look for" hint. Methodology is identical across batches, so the text is hard-coded.

### Auto-generated per-plot narrative (`PlotAnalysis`)

Unlike the static glossary, these are **derived from this batch's actual numbers** and change every run:

- **`_analyze_forest(contributions)`** — buckets components into ✅ improves / ❌ hurts / ⚪ inconclusive (CI crosses zero), tallies the counts, picks an appropriate verdict ("X of Y components proved positive, …") and a recommendation ("disable the inconclusive ones to save tokens" vs "the corpus needs review — current config actively hurts").
- **`_analyze_box(runs)`** — per-config median + IQR; flags noisy vs stable configs (IQR > 0.10 = "noisy"); picks best/worst by median.
- **`_analyze_heatmap(runs)`** — best config and worst (hardest) scenario by mean over seeds; lists the worst three `(config, scenario)` cells if any are below 0.5 meter accuracy.
- **`_analyze_by_category(by_cat)`** — for each category, picks the most-helpful component on the headline metrics; notes that "no significant component" is normal on `normal` (baseline saturates) and abnormal on `edge` / `corner`.

The bullets returned by these analysers contain inline HTML markup (`<code>`, `<b>`) for the Jinja template. The JSON API documents this in the schema docstring; SPAs either render as HTML or strip tags.

### Headline `insights`

`_build_insights(contributions, metadata)` produces:

- **`headline`** — one sentence naming the most-useful component (largest significant positive Δ on a headline metric), or a "no component proved itself" fallback.
- **`component_lines`** — one bullet per (component, metric) pair on `meter_accuracy` and `rhyme_accuracy`, with mean, CI, verdict (`статистично покращує` / `статистично погіршує` / `ефект непостійний`), and a CSS tone tag (`positive` / `negative` / `neutral`) for styling.
- **`cost_lines`** — short summaries built from `metadata["cost"]`: total spend, average per cell, the most expensive config.

### Dashboard URL contracts

The PNG URLs returned by `_plot_urls(batch_dir, metadata)` are served by the FastAPI app's `/results` static mount (configured in [`src/handlers/api/app.py`](../../src/handlers/api/app.py)). Both the HTML page and the JSON consumer can render the images directly without re-uploading them.

---

## Putting it together — a typical workflow

```bash
# 1. Run the matrix (real Gemini, ~270 calls, may take 10–20 min):
make ablation SEEDS=3

# If it dies on a quota error, resume with the same folder:
make ablation BATCH_DIR=results/batch_20260425_204756 RESUME=1

# 2. Build contributions + plots from the CSV:
make ablation-report RUNS=results/batch_20260425_204756/runs.csv

# 3a. Open the HTML dashboard:
make serve   # then http://localhost:8000/ablation-report

# 3b. ...or consume the JSON twin from an SPA:
curl http://localhost:8000/evaluation/ablation-report | jq .
```

Want a faster smoke test? `make ablation SEEDS=1 SCENARIO=N01 CONFIG=E` runs **one** cell — handy for verifying wiring without burning quota.

---

## Key files

- [`Makefile:139-204`](../../Makefile#L139) — `make ablation`, `make ablation-report` recipes and their variables.
- [`scripts/run_batch_evaluation.py`](../../scripts/run_batch_evaluation.py) — argparse wrapper for stage 1.
- [`scripts/analyze_contributions.py`](../../scripts/analyze_contributions.py) — stage 2: paired-Δ + plots + report.json.
- [`src/runners/batch_evaluation_runner.py`](../../src/runners/batch_evaluation_runner.py) — `IRunner` for stage 1 (scenario/config resolution, resume bookkeeping).
- [`src/services/batch_evaluation_service.py`](../../src/services/batch_evaluation_service.py) — the matrix loop with `IDelayer`-injected throttling and streaming writes.
- [`src/domain/evaluation.py`](../../src/domain/evaluation.py) — `AblationConfig`, `BatchRunRow`, `STAGE_*` constants.
- [`src/infrastructure/reporting/csv_batch_results_writer.py`](../../src/infrastructure/reporting/csv_batch_results_writer.py) — flat-row CSV writer + `read_existing_runs` for resume.
- [`src/handlers/shared/ablation_report.py`](../../src/handlers/shared/ablation_report.py) — `build_artifacts()` shared by web and API; static glossary + per-plot analysers + insights builder.
- [`src/handlers/web/routes/ablation_report.py`](../../src/handlers/web/routes/ablation_report.py) — HTML route (thin Jinja wrapper).
- [`src/handlers/api/routers/evaluation.py`](../../src/handlers/api/routers/evaluation.py) — `GET /evaluation/ablation-report` JSON twin.
- [`src/handlers/api/schemas.py`](../../src/handlers/api/schemas.py) — `AblationReportResponseSchema` + helpers.
- [`tests/unit/runners/test_batch_evaluation_runner.py`](../../tests/unit/runners/test_batch_evaluation_runner.py) — orchestration tests with fakes (`FakeBatchService`, `_StubRegistry`).
- [`tests/integration/handlers/api/test_routers.py`](../../tests/integration/handlers/api/test_routers.py) — `TestAblationReportEndpoint` (404 path) + scenarios-by-category + system/llm-info.

---

## Caveats

- **LLM stochasticity is real.** Three seeds is a minimum for the bootstrap CI to be meaningful; for small-effect components, prefer 5+ seeds even if it costs more quota.
- **`regeneration_success` can be negative.** Feedback regeneration can break a previously-OK line. The diverging colour palette on the heatmap surfaces this rather than hiding it inside a 0–1 scale.
- **`expected_to_succeed=False` scenarios** are filtered before the contribution analysis (`_filter_successful` drops rows with non-empty `error`), but they still show up in the heatmap if you don't pass `SKIP_DEGENERATE=1` — useful if you want to *see* the failure pattern, wasteful if you don't.
- **Bootstrap CI is seeded** (`RNG_SEED = 42`). Reports are reproducible byte-for-byte from the same `runs.csv`. If you want randomised CI, change the seed in code — there is no flag for it (deliberate: reproducibility wins).
- **HTML markup in narrative bullets** is part of the contract. JSON consumers that want plain text must strip tags themselves.
