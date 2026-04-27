"""Tests for inverse-metric direction, the two-headline split, and the
new contrast / cluster narrative bullets that the F/G/H configs unlock.
"""
from __future__ import annotations

from src.handlers.shared.ablation_report import (
    _HEADLINE_METRICS,
    _LOWER_IS_BETTER_METRICS,
    _analyze_box,
    _analyze_forest,
    _analyze_heatmap,
    _build_insights,
    _verdict_for,
)


class TestVerdictForInverseMetric:
    def test_negative_delta_on_num_iterations_is_positive_outcome(self):
        verdict, tone = _verdict_for(mean=-0.5, significant=True, metric="num_iterations")
        assert "покращує" in verdict
        assert tone == "positive"

    def test_positive_delta_on_num_iterations_is_negative_outcome(self):
        verdict, tone = _verdict_for(mean=+0.5, significant=True, metric="num_iterations")
        assert "погіршує" in verdict
        assert tone == "negative"

    def test_positive_delta_on_meter_accuracy_is_positive_outcome(self):
        # Sanity: normal metric direction unchanged.
        verdict, tone = _verdict_for(mean=+0.1, significant=True, metric="meter_accuracy")
        assert "покращує" in verdict
        assert tone == "positive"

    def test_non_significant_delta_is_neutral_regardless_of_metric(self):
        for metric in ("num_iterations", "meter_accuracy"):
            _, tone = _verdict_for(mean=+0.1, significant=False, metric=metric)
            assert tone == "neutral"


class TestHeadlineMetricsConfig:
    def test_num_iterations_is_a_headline_metric(self):
        keys = {key for key, _ in _HEADLINE_METRICS}
        assert "num_iterations" in keys

    def test_num_iterations_is_lower_is_better(self):
        assert "num_iterations" in _LOWER_IS_BETTER_METRICS


class TestInsightsBestComponent:
    def test_largest_iteration_reduction_wins_headline(self):
        # Two components: one improves meter by +0.2, another reduces
        # iterations by -0.6. The larger-magnitude effect wins, regardless
        # of metric type.
        contributions = [
            {
                "metric": "meter_accuracy", "component": "rag",
                "mean_delta": 0.2, "ci_low": 0.1, "ci_high": 0.3,
                "significant": True,
            },
            {
                "metric": "num_iterations", "component": "metric_examples",
                "mean_delta": -0.6, "ci_low": -0.8, "ci_high": -0.4,
                "significant": True,
            },
        ]
        insights = _build_insights(contributions, metadata={})
        headline = str(insights["headline"])
        assert "metric_examples" in headline
        # Signed delta preserved (not magnitude) so the user reads
        # «-0.600 на кількість ітерацій», not a confusing «+0.600».
        assert "-0.600" in headline
        assert "ітерацій" in headline

    def test_iteration_increase_does_not_count_as_improvement(self):
        # Component made things worse on iterations; should not headline.
        contributions = [
            {
                "metric": "num_iterations", "component": "bad_thing",
                "mean_delta": +0.4, "ci_low": 0.2, "ci_high": 0.6,
                "significant": True,
            },
        ]
        insights = _build_insights(contributions, metadata={})
        headline = str(insights["headline"])
        # No good effect → fall back message.
        assert "Жоден компонент" in headline or "не показав" in headline


class TestTwoHeadlineSplit:
    """`pure_*` (no-feedback) components must headline separately from
    with-feedback components — they answer different research questions
    and should not compete for the same single "best" slot."""

    def test_both_buckets_surface_when_both_have_winners(self):
        contributions = [
            {
                "metric": "meter_accuracy", "component": "rag_metric_combined",
                "mean_delta": 0.10, "ci_low": 0.05, "ci_high": 0.15,
                "significant": True,
            },
            {
                "metric": "meter_accuracy", "component": "pure_metric_examples",
                "mean_delta": 0.18, "ci_low": 0.10, "ci_high": 0.25,
                "significant": True,
            },
        ]
        insights = _build_insights(contributions, metadata={})
        headline = str(insights["headline"])
        assert "rag_metric_combined" in headline
        assert "pure_metric_examples" in headline
        assert "фінальною якістю" in headline
        assert "raw-якістю" in headline

    def test_only_pure_wins_when_with_feedback_has_no_significant_effect(self):
        contributions = [
            {
                "metric": "meter_accuracy", "component": "pure_semantic_rag",
                "mean_delta": 0.07, "ci_low": 0.02, "ci_high": 0.12,
                "significant": True,
            },
        ]
        insights = _build_insights(contributions, metadata={})
        headline = str(insights["headline"])
        assert "pure_semantic_rag" in headline
        assert "raw-якістю" in headline


class TestFeedbackOverheadCostBullet:
    """Cost analysis must surface the average $-overhead of the feedback
    loop, computed across (no_feedback, with_feedback) pairs of configs."""

    def test_overhead_bullet_emitted_when_per_config_costs_present(self) -> None:
        metadata: dict[str, object] = {
            "cost": {
                "total_tokens": 100_000,
                "total_cost_usd": 1.23,
                "avg_cost_per_run_usd": 0.05,
                "per_config": [
                    {"config": "A", "avg_cost_per_run_usd": 0.01},
                    {"config": "B", "avg_cost_per_run_usd": 0.03},
                    {"config": "F", "avg_cost_per_run_usd": 0.02},
                    {"config": "C", "avg_cost_per_run_usd": 0.05},
                    {"config": "G", "avg_cost_per_run_usd": 0.02},
                    {"config": "D", "avg_cost_per_run_usd": 0.04},
                    {"config": "H", "avg_cost_per_run_usd": 0.03},
                    {"config": "E", "avg_cost_per_run_usd": 0.06},
                ],
            },
        }
        insights = _build_insights(contributions=[], metadata=metadata)
        cost_lines = insights["cost_lines"]
        assert isinstance(cost_lines, list)
        joined = " | ".join(cost_lines)
        assert "Feedback-цикл коштує" in joined
        assert "+$" in joined  # overhead value present


class TestForestContrastBullets:
    """When a `pure_*` and its with-feedback counterpart both have data,
    the forest analysis must add a contrast bullet showing how feedback
    changes the raw effect."""

    def _row(
        self,
        metric: str,
        component: str,
        mean_delta: float,
        sig: bool = True,
    ) -> dict[str, object]:
        ci_lo = mean_delta - 0.05
        ci_hi = mean_delta + 0.05
        return {
            "metric": metric, "component": component,
            "mean_delta": mean_delta, "ci_low": ci_lo, "ci_high": ci_hi,
            "significant": sig,
        }

    def test_contrast_block_emitted_for_pure_with_feedback_pair(self):
        contributions = [
            self._row("meter_accuracy", "semantic_rag", 0.05),
            self._row("meter_accuracy", "pure_semantic_rag", 0.15),
        ]
        analysis = _analyze_forest(contributions)
        joined = " | ".join(analysis.bullets)
        # The contrast header is emitted.
        assert "Контраст" in joined
        # Specific narrative: raw effect bigger → feedback masks it.
        assert "Semantic RAG" in joined
        assert "маскує" in joined

    def test_contrast_bullet_says_paired_when_with_feedback_dominates(self):
        contributions = [
            self._row("meter_accuracy", "metric_examples", 0.20),
            self._row("meter_accuracy", "pure_metric_examples", 0.05),
        ]
        analysis = _analyze_forest(contributions)
        joined = " | ".join(analysis.bullets)
        assert "в парі з feedback" in joined

    def test_contrast_skipped_when_only_one_side_present(self):
        # Only with-feedback comparison, no pure_ counterpart → no
        # contrast bullet (would be misleading).
        contributions = [
            self._row("meter_accuracy", "semantic_rag", 0.05),
        ]
        analysis = _analyze_forest(contributions)
        joined = " | ".join(analysis.bullets)
        assert "Контраст" not in joined


class TestBoxPlotClusterContrast:
    """Box analysis must surface the with-feedback ↔ no-feedback group
    contrast and per-pair gap so the user does not have to lint the
    8-config table by eye."""

    def _runs(self, cfg_to_acc: dict[str, float]) -> list[dict[str, object]]:
        # Build at least 2 rows per config so quantiles work.
        out: list[dict[str, object]] = []
        for cfg, acc in cfg_to_acc.items():
            for seed in (1, 2, 3):
                out.append({
                    "scenario_id": "N01", "config_label": cfg, "seed": seed,
                    "meter_accuracy": acc, "rhyme_accuracy": 1.0,
                    "num_iterations": 0.0,
                })
        return out

    def test_cluster_bullet_compares_feedback_groups(self) -> None:
        runs = self._runs({
            "A": 0.50, "B": 0.80, "C": 0.85, "D": 0.85, "E": 0.90,
            "F": 0.55, "G": 0.65, "H": 0.70,
        })
        analysis = _analyze_box(runs)
        joined = " | ".join(analysis.bullets)
        assert "з feedback" in joined and "без feedback" in joined
        # Pair lines: (B, A), (C, F), (D, G), (E, H) all should appear.
        for nf, wf in (("A", "B"), ("F", "C"), ("G", "D"), ("H", "E")):
            assert f"{wf}</code>−<code>{nf}" in joined or f"{wf}-{nf}" in joined or wf in joined


class TestHeatmapSplitWeakCells:
    """Heatmap weak-cells must split into "real failure modes" (with
    feedback) vs "expected weak" (without feedback). Without this, F-H
    cells flood the failure list and look like system bugs."""

    def _runs(
        self, cell_acc: dict[tuple[str, str], float],
    ) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for (cfg, sid), acc in cell_acc.items():
            for seed in (1, 2):
                out.append({
                    "scenario_id": sid, "config_label": cfg, "seed": seed,
                    "meter_accuracy": acc, "rhyme_accuracy": 1.0,
                    "num_iterations": 0.0,
                })
        return out

    def test_weak_no_feedback_cells_called_out_as_expected(self) -> None:
        # F is weak on N09 (0.30) but E (its with-feedback counterpart)
        # is fine (0.95). Analysis should show F's weakness as expected,
        # not as a real failure.
        runs = self._runs({
            ("A", "N01"): 0.80, ("B", "N01"): 0.95, ("E", "N01"): 0.99,
            ("F", "N01"): 0.85, ("H", "N01"): 0.95,
            ("A", "N09"): 0.40, ("B", "N09"): 0.85, ("E", "N09"): 0.95,
            ("F", "N09"): 0.30, ("H", "N09"): 0.40,
        })
        analysis = _analyze_heatmap(runs)
        joined = " | ".join(analysis.bullets)
        assert "лише серед конфігів без feedback" in joined or "очікувано" in joined

    def test_no_failure_cells_with_feedback_celebrated(self) -> None:
        # All with-feedback configs are above threshold. Should say so.
        runs = self._runs({
            ("A", "N01"): 0.80, ("B", "N01"): 0.95, ("E", "N01"): 0.99,
            ("F", "N01"): 0.30,  # only F (no feedback) is weak
        })
        analysis = _analyze_heatmap(runs)
        joined = " | ".join(analysis.bullets)
        assert "немає" in joined.lower() or "<b>немає</b>" in joined
