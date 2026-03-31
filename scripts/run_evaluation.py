"""Run the full evaluation matrix: scenarios × ablation configs.

Usage:
    python scripts/run_evaluation.py                    # all scenarios, all configs
    python scripts/run_evaluation.py --category normal  # only normal scenarios
    python scripts/run_evaluation.py --scenario N01     # single scenario
    python scripts/run_evaluation.py --config D         # single ablation config
    python scripts/run_evaluation.py --output results/eval.json  # save JSON
    python scripts/run_evaluation.py --verbose          # print full traces
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation.runner import (
    ABLATION_CONFIGS,
    format_markdown_report,
    format_summary_table,
    format_trace_detail,
    run_evaluation_matrix,
)
from src.evaluation.scenarios import (
    ALL_SCENARIOS,
    ScenarioCategory,
    scenario_by_id,
    scenarios_by_category,
)
from src.generation.llm import MockLLMClient, llm_from_env
from src.meter.stress import StressDict
from src.retrieval.corpus import corpus_from_env
from src.retrieval.retriever import SemanticRetriever


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poetry generation evaluation harness")
    p.add_argument("--category", choices=["normal", "edge", "corner"], help="Run only scenarios in this category")
    p.add_argument("--scenario", help="Run a single scenario by ID (e.g. N01, E03, C05)")
    p.add_argument("--config", help="Run a single ablation config (A/B/C/D/E/F)")
    p.add_argument("--metric-examples-path", default="corpus/ukrainian_poetry_dataset.json",
                   dest="metric_examples_path", help="Path to metric examples dataset JSON")
    p.add_argument("--metric-examples-top-k", type=int, default=2, dest="metric_examples_top_k",
                   help="Number of metric examples to inject per run (default: 2)")
    p.add_argument("--max-iterations", type=int, default=1, help="Max feedback iterations (default: 1)")
    p.add_argument("--stanzas", type=int, default=None, help="Override stanza_count for all selected scenarios")
    p.add_argument("--lines-per-stanza", type=int, default=None, dest="lines_per_stanza",
                   help="Override lines_per_stanza for all selected scenarios")
    p.add_argument("--output", "-o", help="Path to save JSON results")
    p.add_argument("--verbose", "-v", action="store_true", help="Print full stage-by-stage traces")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # ── Select scenarios ────────────────────────────────────
    if args.scenario:
        s = scenario_by_id(args.scenario.upper())
        if not s:
            print(f"Unknown scenario ID: {args.scenario}", file=sys.stderr)
            print(f"Available: {[sc.id for sc in ALL_SCENARIOS]}", file=sys.stderr)
            sys.exit(1)
        scenarios = [s]
    elif args.category:
        cat = ScenarioCategory(args.category)
        scenarios = scenarios_by_category(cat)
    else:
        scenarios = list(ALL_SCENARIOS)

    # ── Apply structure overrides ───────────────────────────────
    if args.stanzas is not None or args.lines_per_stanza is not None:
        from dataclasses import replace
        scenarios = [
            replace(
                sc,
                stanza_count=args.stanzas if args.stanzas is not None else sc.stanza_count,
                lines_per_stanza=args.lines_per_stanza if args.lines_per_stanza is not None else sc.lines_per_stanza,
            )
            for sc in scenarios
        ]

    # ── Select configs ──────────────────────────────────────────────────
    if args.config:
        cfg = [c for c in ABLATION_CONFIGS if c.label == args.config.upper()]
        if not cfg:
            print(f"Unknown config: {args.config}. Use A/B/C/D/E", file=sys.stderr)
            sys.exit(1)
        configs = cfg
    else:
        configs = list(ABLATION_CONFIGS)

    # ── Prepare shared resources ────────────────────────────────────────
    print(f"Scenarios: {len(scenarios)}  |  Configs: {len(configs)}  |  Total runs: {len(scenarios) * len(configs)}")
    print()

    llm = llm_from_env() or MockLLMClient()
    stress_dict = StressDict(on_ambiguity="first")
    retriever = SemanticRetriever()
    corpus = corpus_from_env()

    print(f"LLM: {type(llm).__name__}")
    print(f"Corpus: {len(corpus)} poems (CORPUS_PATH={os.getenv('CORPUS_PATH', 'corpus/uk_poetry_corpus.json')})")
    print(f"StressDict: stressify={'YES' if stress_dict._stressify else 'fallback'}")
    print()

    # ── Run ─────────────────────────────────────────────────────────────
    traces, summaries = run_evaluation_matrix(
        scenarios=scenarios,
        configs=configs,
        llm=llm,
        stress_dict=stress_dict,
        retriever=retriever,
        corpus=corpus,
        max_iterations=args.max_iterations,
        metric_examples_path=args.metric_examples_path,
        metric_examples_top_k=args.metric_examples_top_k,
    )

    # ── Print traces (verbose) ──────────────────────────────────────────
    if args.verbose:
        print("=" * 72)
        print("DETAILED TRACES")
        print("=" * 72)
        for trace in traces:
            print(format_trace_detail(trace))

    # ── Print summary table ─────────────────────────────────────────────
    print("=" * 72)
    print("SUMMARY TABLE")
    print("=" * 72)
    print(format_summary_table(summaries))
    print()

    # ── Per-config aggregates ───────────────────────────────────────────
    print("=" * 72)
    print("AGGREGATE BY CONFIG")
    print("=" * 72)
    for cfg in configs:
        cfg_rows = [s for s in summaries if s.config_label == cfg.label]
        if not cfg_rows:
            continue
        avg_meter = sum(r.meter_accuracy for r in cfg_rows) / len(cfg_rows)
        avg_rhyme = sum(r.rhyme_accuracy for r in cfg_rows) / len(cfg_rows)
        avg_iters = sum(r.num_iterations for r in cfg_rows) / len(cfg_rows)
        errors = sum(1 for r in cfg_rows if r.error)
        print(
            f"  Config {cfg.label} ({cfg.description}): "
            f"meter={avg_meter:.2%}  rhyme={avg_rhyme:.2%}  "
            f"avg_iters={avg_iters:.1f}  errors={errors}/{len(cfg_rows)}"
        )
    print()

    # ── Per-category aggregates ─────────────────────────────────────────
    print("=" * 72)
    print("AGGREGATE BY CATEGORY")
    print("=" * 72)
    for cat in ScenarioCategory:
        cat_ids = {s.id for s in scenarios if s.category == cat}
        cat_rows = [s for s in summaries if s.scenario_id in cat_ids]
        if not cat_rows:
            continue
        avg_meter = sum(r.meter_accuracy for r in cat_rows) / len(cat_rows)
        avg_rhyme = sum(r.rhyme_accuracy for r in cat_rows) / len(cat_rows)
        errors = sum(1 for r in cat_rows if r.error)
        print(
            f"  {cat.value.upper()} ({len(cat_ids)} scenarios × {len(configs)} configs = {len(cat_rows)} runs): "
            f"meter={avg_meter:.2%}  rhyme={avg_rhyme:.2%}  errors={errors}"
        )
    print()

    # ── Save JSON + Markdown ────────────────────────────────────────────
    if args.output:
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        payload = {
            "summary": [s.to_dict() for s in summaries],
            "traces": [t.to_dict() for t in traces],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Results saved to {args.output}")

        md_path = os.path.splitext(args.output)[0] + ".md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(format_markdown_report(summaries, traces))
        print(f"Report saved to  {md_path}")


if __name__ == "__main__":
    main()
