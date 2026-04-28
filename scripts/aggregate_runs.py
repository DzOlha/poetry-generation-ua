"""Generate Markdown summary tables from a batch runs.csv.

Reads the flat per-run CSV produced by `make ablation` (one BatchRunRow per
row) and aggregates accuracy / cost / token metrics per scenario category
(Normal / Edge / Corner) for one or all ablation configurations. The tables
are formatted as Markdown so the output is ready to paste into the thesis
or commit alongside the batch results.

Bilingual: pass `--lang ua` (default) or `--lang en` to localize captions.

Usage:
    # Single config to stdout (UA captions by default)
    poetry run python scripts/aggregate_runs.py \
        --runs results/batch_20260426_220040/runs.csv --config A

    # All 8 configs to a single Markdown file (UA)
    poetry run python scripts/aggregate_runs.py \
        --runs results/batch_20260426_220040/runs.csv \
        --output results/batch_20260426_220040/aggregates.ua.md

    # English version
    poetry run python scripts/aggregate_runs.py \
        --runs results/batch_20260426_220040/runs.csv --lang en \
        --output results/batch_20260426_220040/aggregates.en.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from src.domain.evaluation import ABLATION_CONFIGS

# Expected total_lines per scenario — mirrors src/infrastructure/evaluation/scenario_data.py.
EXPECTED_LINES: dict[str, int] = {
    "N01": 4, "N02": 4, "N03": 4, "N04": 8, "N05": 8,
    "E01": 4, "E02": 4, "E03": 4, "E04": 4, "E05": 4,
    "C01": 4, "C02": 4, "C03": 4, "C04": 4, "C05": 4,
    "C06": 4, "C07": 4, "C08": 4,
}

# Order in which categories are displayed in summary tables.
CATEGORY_ORDER = ["normal", "edge", "corner"]
CATEGORY_LABEL = {"normal": "Normal", "edge": "Edge", "corner": "Corner"}
SCENARIO_COUNT = {"normal": 5, "edge": 5, "corner": 8}

# Canonical metadata for each ablation config — pulled from the domain layer
# so the report always reflects the current `enabled_stages` definitions even
# if labels or descriptions evolve.
CONFIG_INFO: dict[str, dict[str, object]] = {
    cfg.label: {
        "description": cfg.description,
        "stages": sorted(cfg.enabled_stages),
    }
    for cfg in ABLATION_CONFIGS
}

# Default order for "all configs" mode — labels in the order declared in the
# domain layer, with any extra labels appended at the end.
ALL_CONFIGS = [cfg.label for cfg in ABLATION_CONFIGS]

# ---------------------------------------------------------------------------
# Localization strings.  Keys are English mnemonics; values are the strings
# rendered in the report.  Ablation-config descriptions themselves stay in
# English (they live in the domain layer as code-level identifiers).
# ---------------------------------------------------------------------------

STRINGS: dict[str, dict[str, str]] = {
    "ua": {
        "report_title": "Зведені показники по конфігураціях ablation-матриці",
        "source": "**Джерело:**",
        "successful_runs": "**Кількість успішних запусків:**",
        "configs_present": "**Конфігурації:**",
        "intro": (
            "Кожна секція показує дві таблиці: усереднені метрики якості "
            "й усереднену економіку (тривалість, токени, вартість) у "
            "розрізі категорій сценаріїв (Normal / Edge / Corner)."
        ),
        "legend_heading": "Легенда конфігурацій",
        "legend_label": "Label",
        "legend_description": "Опис",
        "legend_stages": "Увімкнені стадії",
        "config_heading": "Конфігурація",
        "unknown_config": "(невідома конфігурація)",
        "no_data": "_Дані відсутні у runs.csv._",
        "stages_inline": "**Увімкнені стадії:**",
        "quality_heading": "Підсумкові показники якості — конфігурація",
        "category": "Категорія",
        "scenarios_word": "сценаріїв",
        "lines_match_col": "num_lines = expected",
        "total_row": "Усього",
        "economy_heading": "Економіка — конфігурація",
        "avg_iters": "avg iters",
        "avg_duration": "avg duration (s)",
        "avg_input_tokens": "avg input tokens",
        "avg_output_tokens": "avg output tokens",
        "avg_cost": "avg cost (USD)",
        "total_cost": "total cost (USD)",
    },
    "en": {
        "report_title": "Aggregated metrics across ablation-matrix configurations",
        "source": "**Source:**",
        "successful_runs": "**Successful runs:**",
        "configs_present": "**Configs:**",
        "intro": (
            "Each section shows two tables: averaged quality metrics and "
            "averaged economy (duration, tokens, cost), broken down by "
            "scenario category (Normal / Edge / Corner)."
        ),
        "legend_heading": "Configuration legend",
        "legend_label": "Label",
        "legend_description": "Description",
        "legend_stages": "Enabled stages",
        "config_heading": "Configuration",
        "unknown_config": "(unknown configuration)",
        "no_data": "_No matching rows in runs.csv._",
        "stages_inline": "**Enabled stages:**",
        "quality_heading": "Quality metrics — configuration",
        "category": "Category",
        "scenarios_word": "scenarios",
        "lines_match_col": "num_lines = expected",
        "total_row": "Total",
        "economy_heading": "Economy — configuration",
        "avg_iters": "avg iters",
        "avg_duration": "avg duration (s)",
        "avg_input_tokens": "avg input tokens",
        "avg_output_tokens": "avg output tokens",
        "avg_cost": "avg cost (USD)",
        "total_cost": "total cost (USD)",
    },
}


def t(lang: str, key: str) -> str:
    """Look up a localized string with UA fallback."""
    return STRINGS.get(lang, STRINGS["ua"]).get(key, STRINGS["ua"][key])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Aggregate runs.csv into Markdown summary tables.",
    )
    p.add_argument("--runs", required=True, type=Path,
                   help="Path to runs.csv produced by `make ablation`.")
    p.add_argument("--config", default=None,
                   help="Ablation config label (e.g. A). When omitted, "
                        "every config from runs.csv is rendered.")
    p.add_argument("--output", "-o", default=None, type=Path,
                   help="Write Markdown to this file instead of stdout.")
    p.add_argument("--lang", default="ua", choices=("ua", "en"),
                   help="Caption language for the report. Default: ua.")
    p.add_argument("--include-errors", action="store_true",
                   help="Include rows whose error column is non-empty.")
    return p.parse_args()


def load_runs(path: Path, include_errors: bool) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"Error: file {path} not found.")
    df = pd.read_csv(path)
    if not include_errors and "error" in df.columns:
        df = df[df["error"].fillna("").astype(str).str.strip() == ""]
    df["expected_lines"] = df["scenario_id"].map(EXPECTED_LINES)
    df["lines_match"] = df["num_lines"].astype(int) == df["expected_lines"]
    return df


def aggregate(df_config: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Aggregate one config's rows into (by_category, overall) summaries."""
    by_cat = df_config.groupby("category").agg(
        n=("scenario_id", "count"),
        meter=("meter_accuracy", "mean"),
        rhyme=("rhyme_accuracy", "mean"),
        semantic=("semantic_relevance", "mean"),
        match_rate=("lines_match", "mean"),
        avg_iters=("num_iterations", "mean"),
        avg_dur=("duration_sec", "mean"),
        avg_in=("input_tokens", "mean"),
        avg_out=("output_tokens", "mean"),
        avg_cost=("estimated_cost_usd", "mean"),
        total_cost=("estimated_cost_usd", "sum"),
    )
    overall = pd.Series({
        "n": len(df_config),
        "meter": df_config["meter_accuracy"].mean(),
        "rhyme": df_config["rhyme_accuracy"].mean(),
        "semantic": df_config["semantic_relevance"].mean(),
        "match_rate": df_config["lines_match"].mean(),
        "avg_iters": df_config["num_iterations"].mean(),
        "avg_dur": df_config["duration_sec"].mean(),
        "avg_in": df_config["input_tokens"].mean(),
        "avg_out": df_config["output_tokens"].mean(),
        "avg_cost": df_config["estimated_cost_usd"].mean(),
        "total_cost": df_config["estimated_cost_usd"].sum(),
    })
    return by_cat, overall


def render_config_header(label: str, df_config: pd.DataFrame, lang: str) -> list[str]:
    """Render the title block for a config: label, description, enabled stages."""
    info = CONFIG_INFO.get(label)
    if info is None:
        desc_series = df_config.get("config_description")
        description = (
            desc_series.dropna().iloc[0]
            if desc_series is not None and not desc_series.empty
            else t(lang, "unknown_config")
        )
        stages: list[str] = []
    else:
        description = info["description"]  # type: ignore[assignment]
        stages = info["stages"]  # type: ignore[assignment]
    out = [
        f"## {t(lang, 'config_heading')} {label} — {description}",
        "",
    ]
    if stages:
        out.append(f"{t(lang, 'stages_inline')} `{', '.join(stages)}`")
        out.append("")
    return out


def render_accuracy_table(
    by_cat: pd.DataFrame, overall: pd.Series, label: str, lang: str,
) -> list[str]:
    cat_col = t(lang, "category")
    lines_col = t(lang, "lines_match_col")
    scen_word = t(lang, "scenarios_word")
    out = [
        f"### {t(lang, 'quality_heading')} {label}",
        "",
        f"| {cat_col} | n | meter_accuracy | rhyme_accuracy "
        f"| semantic_relevance | {lines_col} |",
        "|---|---|---|---|---|---|",
    ]
    for cat in CATEGORY_ORDER:
        if cat not in by_cat.index:
            continue
        r = by_cat.loc[cat]
        out.append(
            f"| {CATEGORY_LABEL[cat]} ({SCENARIO_COUNT[cat]} {scen_word}) "
            f"| {int(r['n'])} | {r['meter']:.3f} | {r['rhyme']:.3f} "
            f"| {r['semantic']:.3f} | {r['match_rate']:.0%} |",
        )
    out.append(
        f"| **{t(lang, 'total_row')}** | **{int(overall['n'])}** "
        f"| **{overall['meter']:.3f}** | **{overall['rhyme']:.3f}** "
        f"| **{overall['semantic']:.3f}** | **{overall['match_rate']:.0%}** |",
    )
    return out


def render_economy_table(
    by_cat: pd.DataFrame, overall: pd.Series, label: str, lang: str,
) -> list[str]:
    cat_col = t(lang, "category")
    out = [
        "",
        f"### {t(lang, 'economy_heading')} {label}",
        "",
        f"| {cat_col} | {t(lang, 'avg_iters')} | {t(lang, 'avg_duration')} "
        f"| {t(lang, 'avg_input_tokens')} | {t(lang, 'avg_output_tokens')} "
        f"| {t(lang, 'avg_cost')} | {t(lang, 'total_cost')} |",
        "|---|---|---|---|---|---|---|",
    ]
    for cat in CATEGORY_ORDER:
        if cat not in by_cat.index:
            continue
        r = by_cat.loc[cat]
        out.append(
            f"| {CATEGORY_LABEL[cat]} | {r['avg_iters']:.2f} "
            f"| {r['avg_dur']:.1f} | {int(r['avg_in']):,} "
            f"| {int(r['avg_out']):,} | ${r['avg_cost']:.4f} "
            f"| ${r['total_cost']:.4f} |",
        )
    out.append(
        f"| **{t(lang, 'total_row')}** | **{overall['avg_iters']:.2f}** "
        f"| **{overall['avg_dur']:.1f}** | **{int(overall['avg_in']):,}** "
        f"| **{int(overall['avg_out']):,}** | **${overall['avg_cost']:.4f}** "
        f"| **${overall['total_cost']:.4f}** |",
    )
    return out


def render_config(df: pd.DataFrame, label: str, lang: str) -> list[str]:
    sub = df[df["config_label"] == label]
    if sub.empty:
        info = CONFIG_INFO.get(label, {})
        description = info.get("description", t(lang, "unknown_config"))
        return [
            f"## {t(lang, 'config_heading')} {label} — {description}",
            "",
            t(lang, "no_data"),
            "",
        ]
    by_cat, overall = aggregate(sub)
    return [
        *render_config_header(label, sub, lang),
        *render_accuracy_table(by_cat, overall, label, lang),
        *render_economy_table(by_cat, overall, label, lang),
        "",
    ]


def render_legend(labels: list[str], lang: str) -> list[str]:
    out = [
        f"## {t(lang, 'legend_heading')}",
        "",
        f"| {t(lang, 'legend_label')} | {t(lang, 'legend_description')} "
        f"| {t(lang, 'legend_stages')} |",
        "|---|---|---|",
    ]
    for label in labels:
        info = CONFIG_INFO.get(label)
        if info is None:
            out.append(f"| {label} | {t(lang, 'unknown_config')} | — |")
            continue
        stages = ", ".join(info["stages"])  # type: ignore[arg-type]
        out.append(f"| {label} | {info['description']} | `{stages}` |")
    out.append("")
    return out


def render_full_report(df: pd.DataFrame, runs_path: Path, lang: str) -> str:
    labels_present = sorted(df["config_label"].unique())
    labels = [c for c in ALL_CONFIGS if c in labels_present]
    labels += [c for c in labels_present if c not in ALL_CONFIGS]

    header = [
        f"# {t(lang, 'report_title')}",
        "",
        f"{t(lang, 'source')} `{runs_path}`",
        f"{t(lang, 'successful_runs')} {len(df)}",
        f"{t(lang, 'configs_present')} {', '.join(labels)}",
        "",
        t(lang, "intro"),
        "",
        "---",
        "",
    ]
    legend = render_legend(labels, lang)
    legend.append("---")
    legend.append("")

    body: list[str] = []
    for label in labels:
        body.extend(render_config(df, label, lang))
        body.append("---")
        body.append("")
    return "\n".join(header + legend + body).rstrip() + "\n"


def write_or_print(text: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    sys.stderr.write(f"Wrote {output}\n")


def main() -> None:
    args = parse_args()
    df = load_runs(args.runs, args.include_errors)
    if df.empty:
        sys.exit(f"Error: runs.csv {args.runs} contains no usable rows.")

    if args.config:
        sub = df[df["config_label"] == args.config]
        if sub.empty:
            sys.exit(
                f"Error: no rows for config_label='{args.config}' in {args.runs}.",
            )
        text = "\n".join(render_config(df, args.config, args.lang))
    else:
        text = render_full_report(df, args.runs, args.lang)

    write_or_print(text, args.output)


if __name__ == "__main__":
    main()
