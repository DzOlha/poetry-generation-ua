"""Compute component contributions from a batch runs.csv and render plots.

Pipeline:
  1. Read `runs.csv` (produced by scripts/run_batch_evaluation.py).
  2. For each metric (meter_accuracy, rhyme_accuracy), compute paired
     deltas between ablation configs that isolate a single component:
         feedback_loop        = B − A
         semantic_rag         = C − B
         metric_examples      = D − B
         rag_metric_combined  = E − B
         interaction          = E − C − D + B
     Deltas are paired on (scenario_id, seed) so scenario-difficulty noise
     cancels out.
  3. Bootstrap 95% CI on the mean of each delta set + Wilcoxon signed-rank
     p-value. "Significant" = CI does not cross zero.
  4. Save `contributions.csv`, `contributions_by_cat.csv`, `report.json`.
  5. Render four matplotlib PNGs into `plots/`:
         forest.png             — Δ with CI per component (two metrics)
         box_by_config.png      — meter_accuracy distribution per A–E
         heatmap.png            — mean meter_accuracy, config × scenario
         contribution_by_cat.png — component internals per normal/edge/corner

Run via: python scripts/analyze_contributions.py --runs results/batch_<ts>/runs.csv
Output dir is derived from --runs (sibling artifacts in the same folder).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # noqa: E402  # headless
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

# ---------------------------------------------------------------------------
# Component comparisons (paired delta = minuend − subtrahend)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Comparison:
    component: str
    label: str
    minuend: str
    subtrahend: str


PAIRWISE_COMPARISONS: tuple[Comparison, ...] = (
    # ── Comparisons WITH feedback in both arms ───────────────────────
    # These measure component value at *converged* quality (after the
    # feedback loop has done its work). Useful for "is this stage worth
    # keeping in production?", but the feedback loop partially repairs
    # poor initial drafts, so the raw effect of an enrichment leaks
    # away. Use pure_* comparisons below for the unconfounded picture.
    Comparison("feedback_loop",            "B − A", "B", "A"),
    Comparison("semantic_rag",             "C − B", "C", "B"),
    Comparison("metric_examples",          "D − B", "D", "B"),
    Comparison("rag_metric_combined",      "E − B", "E", "B"),
    # ── Comparisons WITHOUT feedback in either arm ───────────────────
    # Same enrichment vs. baseline, but feedback is OFF so we observe
    # the *first-attempt* quality. This is the right design for "does
    # RAG help the model write better poems out of the gate?" — feedback
    # cannot mask the difference here.
    Comparison("pure_semantic_rag",        "F − A", "F", "A"),
    Comparison("pure_metric_examples",     "G − A", "G", "A"),
    Comparison("pure_rag_metric_combined", "H − A", "H", "A"),
    # ── Marginal value of feedback on top of full enrichment ─────────
    # When everything else is already enabled (RAG + metric examples),
    # how much does the feedback loop still add? Comparing E (full
    # system) to H (full system minus feedback) gives the answer.
    Comparison("feedback_value_full",      "E − H", "E", "H"),
)

METRICS: tuple[str, ...] = (
    "meter_accuracy",
    "rhyme_accuracy",
    "regeneration_success",
    "semantic_relevance",
    "num_iterations",
)

# Metrics where a *lower* value is the desirable outcome. The forest /
# heatmap colour palettes and verdict logic flip sign for these so a
# negative paired-Δ (component reduced the value) is rendered as a win.
# Currently only `num_iterations` belongs here — fewer feedback rounds
# means the LLM produced an acceptable poem on (or closer to) the first
# attempt, which is exactly what RAG / metric examples should help with.
LOWER_IS_BETTER_METRICS: frozenset[str] = frozenset({"num_iterations"})


def _is_improvement(metric: str, delta: float) -> bool:
    """Direction-aware "is this delta good for the user?" check."""
    if metric in LOWER_IS_BETTER_METRICS:
        return delta < 0
    return delta > 0

BOOTSTRAP_ITERATIONS = 10_000
CI_LEVEL = 95.0
RNG_SEED = 42


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def bootstrap_ci(
    samples: np.ndarray,
    n_boot: int = BOOTSTRAP_ITERATIONS,
    ci: float = CI_LEVEL,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean of `samples`."""
    rng = rng or np.random.default_rng(RNG_SEED)
    n = len(samples)
    if n == 0:
        return 0.0, 0.0
    idx = rng.integers(0, n, size=(n_boot, n))
    boot_means = samples[idx].mean(axis=1)
    alpha = (100.0 - ci) / 2.0
    return float(np.percentile(boot_means, alpha)), float(np.percentile(boot_means, 100.0 - alpha))


def wilcoxon_p(deltas: np.ndarray) -> float:
    """Two-sided Wilcoxon signed-rank p-value; returns 1.0 if the test is undefined."""
    # zero_method="wilcox" drops zero deltas; if all samples are zero, scipy raises.
    nonzero = deltas[deltas != 0]
    if len(nonzero) == 0:
        return 1.0
    try:
        return float(stats.wilcoxon(nonzero, zero_method="wilcox").pvalue)
    except ValueError:
        return 1.0


# ---------------------------------------------------------------------------
# Core analyzer
# ---------------------------------------------------------------------------

class ContributionAnalyzer:
    """Pivot runs.csv and compute paired-delta stats per component × metric."""

    def __init__(self, runs: pd.DataFrame) -> None:
        self._runs = _filter_successful(runs)
        self._rng = np.random.default_rng(RNG_SEED)

    def compute_overall(self) -> pd.DataFrame:
        return self._compute(self._runs, category=None)

    def compute_by_category(self) -> pd.DataFrame:
        parts: list[pd.DataFrame] = []
        for cat in sorted(self._runs["category"].dropna().unique()):
            subset = self._runs[self._runs["category"] == cat]
            parts.append(self._compute(subset, category=cat))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # ------------------------------------------------------------------

    def _compute(self, df: pd.DataFrame, *, category: str | None) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for metric in METRICS:
            pivot = df.pivot_table(
                index=["scenario_id", "seed"],
                columns="config_label",
                values=metric,
            )
            for cmp in PAIRWISE_COMPARISONS:
                if cmp.minuend not in pivot.columns or cmp.subtrahend not in pivot.columns:
                    continue
                deltas = (pivot[cmp.minuend] - pivot[cmp.subtrahend]).dropna().to_numpy()
                rows.append(self._stat_row(deltas, cmp.component, cmp.label, metric, category))

            if all(c in pivot.columns for c in ("B", "C", "D", "E")):
                inter = (pivot["E"] - pivot["C"] - pivot["D"] + pivot["B"]).dropna().to_numpy()
                rows.append(self._stat_row(
                    inter, "interaction_rag_metric", "E − C − D + B", metric, category,
                ))
            # No-feedback interaction: do RAG and metric examples
            # synergise (or substitute for each other) when the feedback
            # loop is OFF? Positive H − F − G + A means the combination
            # beats the sum of pure individual effects.
            if all(c in pivot.columns for c in ("A", "F", "G", "H")):
                inter_nf = (pivot["H"] - pivot["F"] - pivot["G"] + pivot["A"]).dropna().to_numpy()
                rows.append(self._stat_row(
                    inter_nf,
                    "interaction_rag_metric_no_feedback",
                    "H − F − G + A",
                    metric,
                    category,
                ))

        return pd.DataFrame(rows)

    def _stat_row(
        self, deltas: np.ndarray, component: str, comparison: str,
        metric: str, category: str | None,
    ) -> dict[str, object]:
        n = int(len(deltas))
        if n == 0:
            return {
                "category": category or "overall",
                "component": component, "comparison": comparison, "metric": metric,
                "n": 0, "mean_delta": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                "p_value": 1.0, "significant": False,
            }
        mean = float(deltas.mean())
        ci_low, ci_high = bootstrap_ci(deltas, rng=self._rng)
        p = wilcoxon_p(deltas)
        return {
            "category": category or "overall",
            "component": component, "comparison": comparison, "metric": metric,
            "n": n, "mean_delta": mean,
            "ci_low": ci_low, "ci_high": ci_high,
            "p_value": p,
            "significant": bool(ci_low > 0 or ci_high < 0),
        }


def _filter_successful(runs: pd.DataFrame) -> pd.DataFrame:
    """Drop runs where the pipeline errored — they have no meaningful metrics."""
    if "error" not in runs.columns:
        return runs
    err = runs["error"].fillna("").astype(str).str.strip()
    return runs[err == ""].copy()


# ---------------------------------------------------------------------------
# Plot renderer
# ---------------------------------------------------------------------------

class PlotRenderer:
    """Builds the four PNGs that back the web /ablation-report page."""

    def __init__(self, runs: pd.DataFrame, contributions: pd.DataFrame,
                 by_cat: pd.DataFrame, output_dir: Path) -> None:
        self._runs = _filter_successful(runs)
        self._contrib = contributions
        self._by_cat = by_cat
        self._out = output_dir
        self._out.mkdir(parents=True, exist_ok=True)

    def render_all(self) -> dict[str, Path]:
        return {
            "forest": self._forest(),
            "box": self._box_by_config(),
            "heatmap": self._heatmap(),
            "by_category": self._contribution_by_category(),
        }

    # ------------------------------------------------------------------

    def _forest(self) -> Path:
        nrows, ncols = _grid_shape(len(METRICS))
        fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.5 * nrows),
                                 sharey=True, squeeze=False)
        flat = axes.flatten()
        for ax, metric in zip(flat, METRICS, strict=False):
            sub = self._contrib[self._contrib["metric"] == metric].copy()
            order = [
                *(c.component for c in PAIRWISE_COMPARISONS),
                "interaction_rag_metric",
                "interaction_rag_metric_no_feedback",
            ]
            sub = sub.set_index("component").reindex(order).reset_index().dropna(subset=["n"])
            y = np.arange(len(sub))
            means = sub["mean_delta"].to_numpy()
            lo = sub["ci_low"].to_numpy()
            hi = sub["ci_high"].to_numpy()
            err = np.vstack([means - lo, hi - means])
            colors = [
                "#16a34a" if row.significant and _is_improvement(metric, row.mean_delta)
                else "#dc2626" if row.significant and row.mean_delta != 0
                else "#9ca3af"
                for row in sub.itertuples()
            ]
            ax.errorbar(means, y, xerr=err, fmt="o", color="#1f2937",
                        ecolor="#1f2937", capsize=4)
            for yi, mi, c in zip(y, means, colors, strict=True):
                ax.scatter([mi], [yi], color=c, s=80, zorder=3)
            ax.axvline(0, color="#6b7280", linestyle="--", linewidth=1)
            ax.set_yticks(y)
            ax.set_yticklabels(sub["component"])
            ax.set_xlabel(f"Δ {metric}")
            ax.set_title(metric)
            ax.grid(axis="x", alpha=0.3)
        for ax in flat[len(METRICS):]:
            ax.axis("off")
        axes[0, 0].invert_yaxis()
        fig.suptitle("Внесок компонента (paired delta з 95% bootstrap CI)")
        fig.tight_layout()
        path = self._out / "forest.png"
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _box_by_config(self) -> Path:
        nrows, ncols = _grid_shape(len(METRICS))
        fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.2 * nrows),
                                 squeeze=False)
        flat = axes.flatten()
        configs = sorted(self._runs["config_label"].unique())
        for ax, metric in zip(flat, METRICS, strict=False):
            data = [self._runs[self._runs["config_label"] == c][metric].to_numpy()
                    for c in configs]
            ax.boxplot(data, tick_labels=configs, showmeans=True,
                       meanprops={"marker": "D", "markerfacecolor": "#2563eb",
                                  "markeredgecolor": "#2563eb", "markersize": 5})
            ax.set_xlabel("конфіг")
            ax.set_ylabel(metric)
            ax.set_title(f"Розподіл {metric} по конфігах")
            ax.grid(axis="y", alpha=0.3)
        for ax in flat[len(METRICS):]:
            ax.axis("off")
        fig.tight_layout()
        path = self._out / "box_by_config.png"
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _heatmap(self) -> Path:
        nrows, ncols = _grid_shape(len(METRICS))
        n_scen = self._runs["scenario_id"].nunique()
        fig, axes = plt.subplots(
            nrows, ncols,
            figsize=(max(9.0, 0.45 * n_scen + 3.0) * ncols, 3.5 * nrows),
            squeeze=False,
        )
        flat = axes.flatten()
        for ax, metric in zip(flat, METRICS, strict=False):
            pivot = self._runs.pivot_table(
                index="config_label", columns="scenario_id", values=metric,
                aggfunc="mean",
            ).sort_index(axis=0).sort_index(axis=1)
            vmin, vmax, cmap = _metric_colorscale(metric, pivot.to_numpy())
            im = ax.imshow(pivot.to_numpy(), aspect="auto", cmap=cmap,
                           vmin=vmin, vmax=vmax)
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
            ax.set_yticks(range(len(pivot.index)))
            ax.set_yticklabels(pivot.index)
            for i in range(pivot.shape[0]):
                for j in range(pivot.shape[1]):
                    v = pivot.iat[i, j]
                    if not np.isnan(v):
                        ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                                fontsize=6.5, color="#1f2937")
            ax.set_xlabel("сценарій")
            ax.set_ylabel("конфіг")
            ax.set_title(f"Середній {metric} (config × scenario)")
            fig.colorbar(im, ax=ax, shrink=0.8, label=metric)
        for ax in flat[len(METRICS):]:
            ax.axis("off")
        fig.tight_layout()
        path = self._out / "heatmap.png"
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path

    def _contribution_by_category(self) -> Path:
        if self._by_cat.empty:
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.text(0.5, 0.5, "Замало даних для розбиття по категоріях",
                    ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            path = self._out / "contribution_by_cat.png"
            fig.savefig(path, dpi=130, bbox_inches="tight")
            plt.close(fig)
            return path

        nrows, ncols = _grid_shape(len(METRICS))
        categories = sorted(self._by_cat["category"].unique())
        components = [c.component for c in PAIRWISE_COMPARISONS]
        x = np.arange(len(categories))
        width = 0.8 / max(len(components), 1)

        fig, axes = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.5 * nrows),
                                 squeeze=False)
        flat = axes.flatten()
        for ax, metric in zip(flat, METRICS, strict=False):
            sub = self._by_cat[self._by_cat["metric"] == metric].copy()
            for i, comp in enumerate(components):
                rows = sub[sub["component"] == comp].set_index("category").reindex(categories)
                means = rows["mean_delta"].to_numpy()
                err = np.vstack([
                    means - rows["ci_low"].to_numpy(),
                    rows["ci_high"].to_numpy() - means,
                ])
                ax.bar(x + i * width - 0.4 + width / 2, means, width,
                       yerr=err, label=comp, capsize=3)
            ax.axhline(0, color="#6b7280", linestyle="--", linewidth=1)
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.set_ylabel(f"Δ {metric}")
            ax.set_title(metric)
            ax.legend(fontsize=7, loc="best")
            ax.grid(axis="y", alpha=0.3)
        for ax in flat[len(METRICS):]:
            ax.axis("off")
        fig.suptitle("Внесок кожного компонента по категоріях сценаріїв")
        fig.tight_layout()
        path = self._out / "contribution_by_cat.png"
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        return path


def _grid_shape(n: int) -> tuple[int, int]:
    """Always 2 columns so subplots stay readable: 1→(1,1), 2→(1,2), 3-4→(2,2), 5-6→(3,2), 7-8→(4,2), …

    The last row holds one subplot if `n` is odd (the unused cell is hidden by
    callers via ``ax.axis("off")``). Two columns avoid the squashed 2×3 layout
    that made every chart unreadably narrow on standard report widths.
    """
    if n <= 1:
        return (1, 1)
    cols = 2
    rows = (n + cols - 1) // cols
    return (rows, cols)


def _metric_colorscale(metric: str, values: np.ndarray) -> tuple[float, float, str]:
    """Pick (vmin, vmax, cmap) for a heatmap cell grid.

    regeneration_success can be negative (feedback can degrade quality) — use
    a symmetric diverging palette centred on zero. num_iterations is bounded
    [0, max_iterations] but lower is better, so we use the reversed
    green-to-red palette and let the actual data range drive the scale.
    The other three metrics live in [0, 1] so a fixed green-to-red scale
    is unambiguous.
    """
    if metric == "regeneration_success":
        finite = values[np.isfinite(values)]
        bound = float(np.max(np.abs(finite))) if finite.size else 0.1
        bound = max(bound, 0.05)
        return (-bound, bound, "RdBu_r")
    if metric in LOWER_IS_BETTER_METRICS:
        finite = values[np.isfinite(values)]
        vmax = float(np.max(finite)) if finite.size else 1.0
        vmax = max(vmax, 1.0)  # avoid degenerate (0,0) range when no iters happened
        return (0.0, vmax, "RdYlGn_r")
    return (0.0, 1.0, "RdYlGn")


# ---------------------------------------------------------------------------
# Cost / token summary
# ---------------------------------------------------------------------------

_TOKEN_COLS: tuple[str, ...] = (
    "input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd",
)


def _cost_summary(df: pd.DataFrame) -> dict[str, object]:
    """Total + per-config token & cost aggregates for the whole batch.

    Returns zeros (not "missing") when token columns are absent so the
    web template's numeric formatters do not need special-casing. Per-run
    averages are just totals divided by run count — analysts converting to
    "cost per poem" in slides rarely need more precision than that.
    """
    have_tokens = all(col in df.columns for col in _TOKEN_COLS)
    if not have_tokens or df.empty:
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "avg_tokens_per_run": 0.0,
            "avg_cost_per_run_usd": 0.0,
            "per_config": [],
        }

    ok = _filter_successful(df)
    total_input = int(ok["input_tokens"].sum())
    total_output = int(ok["output_tokens"].sum())
    total_tokens = int(ok["total_tokens"].sum())
    total_cost = float(ok["estimated_cost_usd"].sum())
    n = max(1, len(ok))

    per_config: list[dict[str, object]] = []
    for label, grp in ok.groupby("config_label"):
        per_config.append({
            "config": str(label),
            "runs": int(len(grp)),
            "input_tokens": int(grp["input_tokens"].sum()),
            "output_tokens": int(grp["output_tokens"].sum()),
            "total_tokens": int(grp["total_tokens"].sum()),
            "total_cost_usd": float(grp["estimated_cost_usd"].sum()),
            "avg_tokens_per_run": float(grp["total_tokens"].mean()),
            "avg_cost_per_run_usd": float(grp["estimated_cost_usd"].mean()),
        })
    per_config.sort(key=lambda r: str(r["config"]))

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "avg_tokens_per_run": float(total_tokens) / n,
        "avg_cost_per_run_usd": total_cost / n,
        "per_config": per_config,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(runs_csv: Path) -> None:
    if not runs_csv.exists():
        raise SystemExit(f"runs.csv not found: {runs_csv}")

    output_dir = runs_csv.parent
    plots_dir = output_dir / "plots"

    df = pd.read_csv(runs_csv)
    analyzer = ContributionAnalyzer(df)
    overall = analyzer.compute_overall()
    by_cat = analyzer.compute_by_category()

    overall.to_csv(output_dir / "contributions.csv", index=False)
    by_cat.to_csv(output_dir / "contributions_by_cat.csv", index=False)

    renderer = PlotRenderer(df, overall, by_cat, plots_dir)
    plot_paths = renderer.render_all()

    cost = _cost_summary(df)

    report = {
        "batch_id": output_dir.name,
        "runs_csv": str(runs_csv.relative_to(output_dir.parent.parent))
            if runs_csv.is_absolute() else str(runs_csv),
        "total_runs": int(len(df)),
        "error_runs": int(len(df) - len(_filter_successful(df))),
        "seeds": int(df["seed"].nunique()) if "seed" in df.columns else 0,
        "n_scenarios": int(df["scenario_id"].nunique()) if "scenario_id" in df.columns else 0,
        "n_configs": int(df["config_label"].nunique()) if "config_label" in df.columns else 0,
        "configs": sorted(df["config_label"].unique().tolist())
            if "config_label" in df.columns else [],
        "metrics": list(METRICS),
        "components": [c.component for c in PAIRWISE_COMPARISONS]
            + ["interaction_rag_metric", "interaction_rag_metric_no_feedback"],
        "plots": {k: str(p.relative_to(output_dir)) for k, p in plot_paths.items()},
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "ci_level": CI_LEVEL,
        "cost": cost,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote contributions.csv, contributions_by_cat.csv, report.json, "
          f"plots/ into {output_dir}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description="Compute ablation contributions + plots")
    p.add_argument("--runs", required=True, type=Path,
                   help="Path to runs.csv produced by scripts/run_batch_evaluation.py")
    args = p.parse_args()
    run(args.runs)


if __name__ == "__main__":
    main()
