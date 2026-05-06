# How ablation reports work — plain-language guide

> This document is the *intuition-only* companion to `make ablation-report`. If you want formulas, code paths, and academic citations, read [`ablation_batch_and_report.md`](./ablation_batch_and_report.md). Here we trade rigour for clarity.

## The analogy

Imagine you're testing a new study technique. You take 18 students. Each writes the same exam twice: once using the old method, once using the new. The question: is the new method actually better, or did we just get a lucky cohort?

In our case, the "students" are **test scenarios**, the "method" is the **system configuration** (which components are switched on), and the "exam score" is a **poem-quality metric** (meter accuracy, rhyme accuracy, etc.).

## Our cohort: 18 scenarios

Each scenario is a fixed `(theme, metre, foot count, rhyme scheme, structure)` request. The matrix is split into three categories:

**5 NORMAL — typical, easy for the system:**

| ID | Theme | Metre | Feet | Rhyme |
|---|---|---|---|---|
| N01 | Spring in a forest | iamb | 4 | ABAB |
| N02 | Love | trochee | 4 | AABB |
| N03 | Homeland | dactyl | 4 | ABBA |
| N04 | Loneliness | amphibrach | 4 | ABAB |
| N05 | City at night | anapest | 4 | AABB |

**5 EDGE — boundary but legitimate:**

| ID | What it tests |
|---|---|
| E01 | Very short line (iamb, 2-foot, AABB) |
| E02 | Alexandrine (iamb, 6-foot, ABAB) |
| E03 | Rare combination (anapest, 6-foot, ABBA) |
| E04 | Monorhyme — strictest rhyme constraint (amphibrach, 5-foot, AAAA) |
| E05 | Abstract theme with no close RAG neighbours (dactyl, 5-foot, ABAB) |

**8 CORNER — adversarial robustness tests:**

| ID | What it tests |
|---|---|
| C01 | Minimal theme — single word "тиша" (trochee 6-foot, ABAB) |
| C02 | Very long theme, >200 chars (iamb 5-foot, ABAB) |
| C03 | Theme in English (dactyl 3-foot, ABAB) |
| C04 | Non-existent metre "hexameter" (4-foot, ABAB) — expected to fail |
| C05 | Single line (1-foot anapest) |
| C06 | Emoji + HTML in the theme (amphibrach 6-foot, AABB) |
| C07 | Mixed Ukrainian + Russian (iamb 4-foot, ABAB) |
| C08 | Zero feet (trochee 0-foot, ABAB) — expected to fail |

All 18 are different. Each has its own intrinsic difficulty: N01 (typical spring, iamb) is easy, C04 (hexameter) is impossible by design. That is normal — telling apart "the component helps" from "we drew an easy scenario" is the **whole job of the statistics**.

## The "method variants": 8 configurations A–H

Each configuration toggles three key system components:

| Config | Semantic RAG | Metric Examples | Feedback loop |
|---|---|---|---|
| A | ❌ | ❌ | ❌ |
| B | ❌ | ❌ | ✅ |
| C | ✅ | ❌ | ✅ |
| D | ❌ | ✅ | ✅ |
| **E** (full system) | ✅ | ✅ | ✅ |
| F | ✅ | ❌ | ❌ |
| G | ❌ | ✅ | ❌ |
| H | ✅ | ✅ | ❌ |

`A` is the baseline — only the validator, none of the smart components. `E` is the full system. The others are combinations.

`18 scenarios × 8 configs = 144 runs`, which is one full pass of `make batch SEEDS=1`. Each run is a paid LLM call that takes minutes. We cannot run this forever.

## Step 1. Pair each scenario with itself

Suppose we want to measure whether the feedback loop helps. We take two configs that differ **only** by the feedback toggle:

- A = baseline, no feedback
- B = baseline + feedback

Now for **each** scenario we record A's result and B's result. Two exams, same student:

| Scenario | A (no feedback) | B (with feedback) | Δ = B − A |
|---|---|---|---|
| N01 (Spring, iamb) | 0.72 | 0.80 | +0.08 |
| N02 (Love, trochee) | 0.68 | 0.80 | +0.12 |
| E02 (alexandrine) | 0.40 | 0.50 | +0.10 |
| E03 (anapest 6-foot) | 0.49 | 0.55 | +0.06 |
| C04 (hexameter) | 0.60 | 0.56 | −0.04 |
| C06 (emoji theme) | 0.60 | 0.65 | +0.05 |

Numbers are hypothetical but realistic. Δ vector: `[+0.08, +0.12, +0.10, +0.06, −0.04, +0.05]`. In a real run there are 18 such numbers, one per scenario — we picked 6 for the example so the picture stays readable.

**Why MUST we compare like-for-like?** Because the scenarios differ wildly in difficulty. If we naively did `mean(B) − mean(A)`:
- Suppose A had been run mostly on N01–N05 (easy) → mean A = 0.70.
- Suppose B had been run mostly on C04 / C08 (broken by design) → mean B = 0.55.
- Naive: `mean(B) − mean(A) = −0.15`. Verdict: "B makes it worse".

But we compared different problems entirely — easy ones with the old method, broken ones with the new. Pairing kills this once and for all: every Δ is measured on **the same scenario**. Scenario difficulty is paired out, all that remains is the contribution of the toggled component.

## Step 2. Can we trust those 18 numbers?

Suppose our Δ vector is mostly positive. Did we get lucky, or does the component genuinely help? Maybe a different set of scenarios would have shown the opposite? That is what **bootstrap** answers.

Bootstrap is a thought experiment: *"pretend these 18 scenarios are your entire universe, then redraw 18 of them with replacement"*. Concretely:

1. Randomly pick 18 numbers from our 18-element Δ vector — **with replacement** (we can take N01's Δ twice and skip C04's Δ entirely). It is like rolling an 18-sided die 18 times.
2. Compute the mean of that resample. Remember it.
3. Do this **10 000 times**. You now have 10 000 "possible means".
4. Sort them. Take the 2.5th percentile and the 97.5th percentile. 95 % of the plausible means fall between those two values.

For our Δ vector the bootstrap might return, say, `CI ≈ [+0.02, +0.10]`. The interval lies **entirely above zero** → we say "`feedback_loop` reliably improves `meter_accuracy`". That is the **`significant = True`** flag in `contributions.csv`.

If the CI had come out `[−0.02, +0.13]` — still positive on average, but the lower bound dips below zero → the effect *could* be zero given the variation → `significant = False`, we don't insist.

## Step 3. Wilcoxon — a second opinion

This is a different way of asking the same question. The Wilcoxon signed-rank test asks: "*if the component had no effect at all, how rare would this pattern of Δ signs and magnitudes be*?". It returns a p-value: small (0.01) → "this pattern would be very rare under the null, so the effect is probably real"; large (0.5) → "nothing unusual, can't say".

**Why we keep it in the CSV but don't use it for verdicts.**

Why we keep it: it is an *independent second opinion*. If the CI says "significant" but Wilcoxon's p = 0.9, that is a red flag to inspect the raw Δ vector by hand (maybe all the Δs are identical because of a caching bug). Normally CI and p tell the same story; disagreement is a diagnostic signal. Plus computing it is essentially free — one `scipy.stats.wilcoxon` call, ~20 µs. Plus a paper reviewer will always expect to see a p alongside an effect.

Why we do not use it for verdicts: at our `n = 18` Wilcoxon is too **conservative**. It misses real effects. In the example above 5 of 6 Δs are positive and all sizeable — the pattern is visually unambiguous — but `p ≈ 0.06–0.12`. If we drove verdicts off `p < 0.05`, we would discard this perfectly real effect as "non-significant". The CI on the same data calmly reports "average ≈ 0.06, definitely above zero, definitely below 0.10" — and that is enough to decide.

## Step 4. Interaction between the two RAG variants

We have two enhancement components: semantic RAG (thematic examples) and metric examples (rhythmic templates). The question: when both are turned on, do they exceed the sum of their individual effects (synergy)? Are they exactly additive (independent)? Or do they fight each other (competition)?

Take four configs (all on top of baseline-feedback `B`):

|  | semantic OFF | semantic ON |
|---|---|---|
| **metric OFF** | B (feedback only) | C (+ semantic) |
| **metric ON** | D (+ metric) | E (full system) |

If the effects **just add up**: `E_predicted = B + (C − B) + (D − B) = C + D − B`. The "residual" — what we actually saw in E minus this prediction — is:

```
Δ_interaction = E − (C + D − B) = E − C − D + B
```

| Sign | Interpretation |
|---|---|
| `> 0` | **Synergy** — together they exceed the sum of individual contributions. Signal: "turn on both". |
| `≈ 0` | **Additive** — the components are independent, effects just add. |
| `< 0` | **Competition** — one suppresses the other (perhaps fighting for the prompt budget). |

The same formula is applied to the feedback-OFF half of the matrix: `H − F − G + A` gives an interaction **with feedback-loop excluded**. That tells you whether the synergy is intrinsic to the two RAG variants, or whether the feedback loop creates it.

## Why these specific numbers

| Knob | Value | Why |
|---|---|---|
| 18 scenarios | 5 NORMAL + 5 EDGE + 8 CORNER | Size of the evaluation matrix in [`scenarios.py`](../../src/infrastructure/evaluation/scenario_data.py). More — too expensive in LLM tokens; fewer — the statistics fall apart. |
| 8 configs A–H | 2³ ways to toggle three components | Full 2×2×2 factorial grid for three independent components. |
| `SEEDS = 1` | one run per cell | Default; each extra seed adds another full 144-call pass. For weak effects, bump to `SEEDS = 3`. |
| 10 000 bootstrap iterations | standard | More — no visible improvement in CI; fewer — CI becomes noisy across runs. |
| 95 % CI | reporting standard | 99 % would widen every interval and almost nothing would be "significant" at our sample sizes. |
| `RNG_SEED = 42` | reproducibility | Reports are byte-identical given the same CSV. |

## What the reader of the report actually sees

`make ablation-report` produces a dashboard with:

1. **Forest plot** — for each component (feedback_loop, semantic_rag, metric_examples, …) a dot with an error bar `[ci_low, ci_high]`. Green dot = significant positive (CI above zero). Red = significant negative. Grey = CI crosses zero (effect inconclusive).
2. **Box plot** — distribution of each metric across the 8 configs A–H. Reveals "noisy" configs (tall box) and best/worst by median.
3. **Heatmap (config × scenario)** — exactly where the failures are. Red columns = scenarios no config solves (typically C04 "hexameter" and C08 "0 feet" — designed to fail). Red rows = bad configs (usually A — baseline).
4. **Per-category breakdown** — the same paired-Δ + CI as the forest plot, split by `normal` / `edge` / `corner`. Common pattern: components are nearly neutral on NORMAL (already saturated) but help on EDGE / CORNER.

A separate dashboard block is the auto-generated **narrative**: what this specific batch said, which components were the most useful, where the failures clustered. It is auto-assembled from `contributions.csv` + `report.json`.

---

> Deeper coverage with formulas and code — [`ablation_batch_and_report.md`](./ablation_batch_and_report.md). The scenario list with motivation behind each — `scenarios.py` and [`evaluation_harness.md`](./evaluation_harness.md).
