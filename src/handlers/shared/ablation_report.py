"""Ablation-report artifact builder — shared between web and API handlers.

Reads the latest `results/batch_*/` folder produced by Stage 1+2 of the
ablation pipeline and assembles a single value object that contains
everything the dashboard needs:

  * the raw `report.json` metadata (token totals, batch parameters, etc.);
  * the `contributions.csv` and `contributions_by_cat.csv` paired-Δ rows;
  * URLs of the four PNG plots served from `/results/<batch>/plots/`;
  * a static glossary explaining each ablation component;
  * static plot-explanation captions (methodology — same across batches);
  * **per-plot auto-generated narrative analyses** computed from the
    actual numbers (these change per batch);
  * a scenario catalogue grouped by category (NORMAL / EDGE / CORNER);
  * a config catalogue (A–H; E is the recommended default) with long human-friendly descriptions;
  * a top-level "insights" block: headline sentence + per-(component,
    metric) verdicts + optional cost summary.

Both the HTML route (`/ablation-report`) and the JSON API endpoint
(`/evaluation/ablation-report`) call `build_artifacts()` and render the
same payload — the JSON serialisation lives in the schema layer, the
HTML rendering lives in the Jinja template.

No pandas at runtime — uses stdlib `csv` and `json` so this builder
works even when the analysis dev-dependencies are not installed.

NOTE on HTML markup: the per-plot analyses (`PlotAnalysis.bullets` and
`.summary`) and the per-category insight bullets contain inline HTML
tags (``<code>``, ``<b>``) for template rendering. Consumers that
serialise these as JSON should either render them as HTML or strip
the tags client-side — the markup is part of the contract.
"""
from __future__ import annotations

import contextlib
import csv
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from src.domain.evaluation import ABLATION_CONFIGS
from src.domain.ports import IScenarioRegistry
from src.domain.values import ScenarioCategory

# ---------------------------------------------------------------------------
# Static narrative tables
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ComponentExplanation:
    """One row of the component glossary shown above the contributions table."""

    name: str
    label: str
    comparison: str
    summary: str
    interpretation: str


COMPONENT_GLOSSARY: tuple[ComponentExplanation, ...] = (
    ComponentExplanation(
        name="feedback_loop",
        label="Feedback-цикл",
        comparison="B − A",
        summary=(
            "Ефект увімкнення feedback-циклу поверх baseline. "
            "Конфіг A — це лише початкова генерація + валідатор; "
            "конфіг B додає одну спробу регенерації, де LLM отримує "
            "формалізований опис порушень метру/рими і має їх виправити."
        ),
        interpretation=(
            "Δ > 0 і CI не перетинає 0 → регенерація з фідбеком справді "
            "підтягує якість. Якщо CI перетинає 0, ефект непостійний — "
            "fb рятує одні випадки і ламає інші, у середньому ~нуль."
        ),
    ),
    ComponentExplanation(
        name="semantic_rag",
        label="Семантичний RAG",
        comparison="C − B",
        summary=(
            "Ефект увімкнення semantic-retrieval (LaBSE-embedding пошук "
            "у тематичному корпусі) поверх вже-увімкненого feedback-циклу. "
            "Конфіг C дає промпту 2 найближчі за смислом приклади віршів."
        ),
        interpretation=(
            "Очікуємо позитивний ефект на semantic_relevance і нейтральний "
            "на meter/rhyme. Якщо meter/rhyme падає — RAG приніс «шумні» "
            "приклади і LLM почала наслідувати їхні помилки замість теми."
        ),
    ),
    ComponentExplanation(
        name="metric_examples",
        label="Метрико-римові приклади",
        comparison="D − B",
        summary=(
            "Ефект увімкнення підбору прикладів за метро-римовою схемою "
            "(few-shot із корпусу віршів того самого розміру/римування). "
            "Конфіг D показує LLM 2 приклади з ідентичним метром+римою."
        ),
        interpretation=(
            "Орієнтуємось на ріст meter_accuracy / rhyme_accuracy. "
            "Якщо Δ помітно більше за RAG-Δ — формальні приклади працюють "
            "краще за тематичні, бо LLM копіює структуру, а не зміст."
        ),
    ),
    ComponentExplanation(
        name="rag_metric_combined",
        label="RAG + метрико-приклади (разом)",
        comparison="E − B",
        summary=(
            "Ефект увімкнення обох RAG-механізмів одночасно поверх "
            "feedback-baseline. Конфіг E — повна система."
        ),
        interpretation=(
            "Це сумарний ефект двох компонентів з потенційною інтеракцією. "
            "Якщо ≈ semantic_rag + metric_examples — компоненти ортогональні. "
            "Якщо менше — вони конкурують за місце в промпті чи за увагу LLM."
        ),
    ),
    ComponentExplanation(
        name="interaction_rag_metric",
        label="Взаємодія RAG ↔ метрико-приклади",
        comparison="E − C − D + B",
        summary=(
            "Чиста 2-way interaction: чи додають RAG і metric-examples "
            "разом *більше*, ніж сума їхніх окремих ефектів."
        ),
        interpretation=(
            "Δ > 0 → синергія: разом краще, ніж сума частин. "
            "Δ ≈ 0 → ефекти просто складаються, нічого нового. "
            "Δ < 0 → конкуренція або витіснення (один компонент «глушить» інший)."
        ),
    ),
    # ── Pure (no-feedback) component effects ───────────────────────────
    ComponentExplanation(
        name="pure_semantic_rag",
        label="Чистий semantic RAG (без feedback)",
        comparison="F − A",
        summary=(
            "Ефект RAG на якість *першого* драфту, без жодних подальших "
            "виправлень. Конфіг F — тематичний пошук + валідатор, але "
            "без feedback-циклу. Так ми бачимо, чи RAG допомагає LLM "
            "написати кращий вірш одразу, а не лише полегшує роботу "
            "feedback-у."
        ),
        interpretation=(
            "Порівняй із semantic_rag (C − B). Якщо чистий ефект більший — "
            "feedback частково «маскує» внесок RAG, бо репарує погані "
            "початкові варіанти. Якщо приблизно однаковий — RAG корисний "
            "стабільно. Якщо чистий ефект слабкий — RAG потребує feedback-у, "
            "щоб довести роботу до кінця."
        ),
    ),
    ComponentExplanation(
        name="pure_metric_examples",
        label="Чисті метрико-приклади (без feedback)",
        comparison="G − A",
        summary=(
            "Аналогічний контроль для metric-examples: G — few-shot "
            "приклади за метро-римовою схемою + валідатор, без feedback. "
            "Ключова метрика для перевірки гіпотези «metric examples "
            "скорочують ітерації»: якщо G − A на meter/rhyme accuracy "
            "значно > 0, то LLM уже з першого разу пише правильніше."
        ),
        interpretation=(
            "Відповідає на питання: чи допомагають metric-приклади самі по "
            "собі, чи лише в парі з feedback-репарацією. Великий чистий "
            "ефект на meter_accuracy → so few-shot достатньо для метру. "
            "Малий ефект → feedback робить основну роботу."
        ),
    ),
    ComponentExplanation(
        name="pure_rag_metric_combined",
        label="Чистий RAG + metric examples (без feedback)",
        comparison="H − A",
        summary=(
            "Сумарний ефект обох збагачень на якість першого драфту, "
            "без feedback. Конфіг H — повна система мінус feedback-цикл."
        ),
        interpretation=(
            "Порівняй із rag_metric_combined (E − B): різниця говорить, "
            "наскільки feedback ще «дотягує» якість поверх вже багатого "
            "промпту, а наскільки — лише дорогий шум."
        ),
    ),
    ComponentExplanation(
        name="feedback_value_full",
        label="Чистий внесок feedback на повному стеку",
        comparison="E − H",
        summary=(
            "Маргінальна цінність feedback-циклу, коли все інше (RAG + "
            "metric examples) уже увімкнене. Тобто: коли промпт уже "
            "максимально багатий, чи має сенс ще й крутити цикл "
            "виправлень, чи це лише марнування токенів."
        ),
        interpretation=(
            "Δ > 0 → feedback все ще корисний навіть з повним RAG. "
            "Δ ≈ 0 → промпт уже зробив усе, що можна; feedback зайвий. "
            "Δ < 0 → feedback ламає вже-добрий вірш (рідко, але можливо)."
        ),
    ),
    ComponentExplanation(
        name="interaction_rag_metric_no_feedback",
        label="Взаємодія RAG ↔ metric examples (без feedback)",
        comparison="H − F − G + A",
        summary=(
            "Те саме що interaction_rag_metric, але без впливу feedback-"
            "циклу. Чиста синергія/конкуренція двох компонентів."
        ),
        interpretation=(
            "Δ > 0 → компоненти підсилюють один одного на першому драфті. "
            "Δ ≈ 0 → ортогональні. Δ < 0 → борються за місце в промпті."
        ),
    ),
)


@dataclass(frozen=True)
class PlotExplanation:
    """Caption shown beneath each plot heading."""

    title: str
    what: str
    how_to_read: str
    look_for: str


@dataclass(frozen=True)
class PlotAnalysis:
    """Auto-generated commentary derived from the actual numbers.

    Unlike :class:`PlotExplanation` (static reference text — same for every
    batch), this is computed per-batch from runs.csv / contributions.csv
    so the commentary describes *this* report, not the methodology in
    general.

    NOTE: ``summary`` and entries in ``bullets`` may contain inline HTML
    tags (``<code>``, ``<b>``) for template rendering.
    """

    summary: str          # 1–2 sentence headline observation
    bullets: list[str]    # follow-up observations / conclusions
    empty: bool = False   # True when no data was available to analyse


PLOT_GLOSSARY: dict[str, PlotExplanation] = {
    "forest": PlotExplanation(
        title="Forest plot — внесок кожного компонента",
        what=(
            "Точка = середня різниця (Δ) метрики між двома конфігами на "
            "однакових (scenario, seed)-парах. «Вуса» — 95% bootstrap CI "
            "цього середнього (10 000 ресемплінгів)."
        ),
        how_to_read=(
            "Зелена точка — компонент статистично покращує метрику "
            "(CI повністю > 0). Червона — статистично шкодить (CI < 0). "
            "Сіра — ефект непостійний, CI перетинає 0."
        ),
        look_for=(
            "Подивіться, які компоненти варто залишити (зелені на ваших "
            "пріоритетних метриках) і які можна вимкнути для економії "
            "токенів (сірі / червоні), бо їхній внесок не доведений."
        ),
    ),
    "box": PlotExplanation(
        title="Box plot — розподіл метрик по конфігах",
        what=(
            "Boxplot для кожного з 8 конфігів A–H на сирих значеннях meter / "
            "rhyme / regen / semantic — без парування. Видно медіану, "
            "квартилі, викиди і середнє (сині ромбики). A–E мають feedback, "
            "F–H — ні (для виміру raw-внеску)."
        ),
        how_to_read=(
            "Висота «коробки» — спред типових результатів. Точки за «вусами» "
            "— викиди. Боксплот не показує статистичної значущості різниць; "
            "це лише сирий розподіл, з якого виростає Δ у forest plot."
        ),
        look_for=(
            "Низькі бокси = стабільний конфіг. Високі або «бруднозажирні» "
            "бокси = шумний конфіг із великою дисперсією. Якщо медіана "
            "конфігу E помітно вища за A — повна система реально підвищує "
            "якість, а не лише в окремих випадках."
        ),
    ),
    "heatmap": PlotExplanation(
        title="Heatmap — конфіг × сценарій",
        what=(
            "Кожна клітинка = середнє значення метрики на цій парі "
            "(конфіг × сценарій), усереднене по всіх seed'ах."
        ),
        how_to_read=(
            "Зелене = висока метрика, червоне = низька. Для "
            "regeneration_success — диверсна шкала (синє = погіршення, "
            "червоне = покращення відносно нуля)."
        ),
        look_for=(
            "Червоні стовпці = «складні» сценарії, які жоден конфіг не "
            "розв'язав → треба покращувати pipeline. Червоні рядки = "
            "проблемні конфіги. Зелені рядки знизу-зверху = повна "
            "система впорається з найбільшою кількістю кейсів."
        ),
    ),
    "by_category": PlotExplanation(
        title="Внесок компонентів по категоріях сценаріїв",
        what=(
            "Той самий paired-Δ і CI, що й у forest plot, але окремо для "
            "категорій scenario-набору: normal / edge / corner. "
            "Кожен компонент — окрема серія стовпчиків."
        ),
        how_to_read=(
            "Висота стовпчика — середнє Δ; помилкові смужки — 95% CI. "
            "Стовпчик > 0 з вусами що не торкаються 0 → компонент "
            "статистично допомагає у саме цій категорії."
        ),
        look_for=(
            "Часта картина: компонент майже нейтральний на normal-сценаріях "
            "і дає великий приріст на edge/corner — там, де baseline "
            "стикається з нестандартними кейсами і має «куди рости»."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Catalogues from domain data
# ---------------------------------------------------------------------------

_CATEGORY_LABELS: dict[ScenarioCategory, str] = {
    ScenarioCategory.NORMAL: "Звичайні (normal)",
    ScenarioCategory.EDGE: "Граничні (edge)",
    ScenarioCategory.CORNER: "Корнер-кейси (corner)",
}

_CATEGORY_BLURB: dict[ScenarioCategory, str] = {
    ScenarioCategory.NORMAL: (
        "Поширені поетичні форми української традиції. Очікуємо, що "
        "baseline впорається без зовнішніх компонентів, тому Δ тут "
        "часто близькі до нуля — це не «погано», а нормально."
    ),
    ScenarioCategory.EDGE: (
        "Незвичайні комбінації метру, стопи чи римування (моноримна, "
        "дуже коротка/довга, абстрактна тема). Тут зазвичай і виявляється, "
        "які саме компоненти витягують якість."
    ),
    ScenarioCategory.CORNER: (
        "Свідомо «погані» кейси: порожня тема, латиниця, спецсимволи, "
        "нульова кількість стоп. Перевіряють робастність pipeline'у — "
        "що нічого не падає, а не якість поезії."
    ),
}


_CONFIG_HUMAN_DESC: dict[str, str] = {
    "A": (
        "Baseline. Лише початкова генерація + валідатор. Без regeneration, "
        "без RAG, без few-shot прикладів. Точка відліку — те, що LLM "
        "вміє «з порога»."
    ),
    "B": (
        "A + feedback-цикл. Якщо валідатор знайшов порушення, LLM отримує "
        "формалізований опис помилки і одну спробу їх виправити."
    ),
    "C": (
        "B + semantic RAG. У промпт додаються 2 найближчі за темою вірші "
        "з тематичного корпусу (LaBSE-embedding пошук). Стиль/настрій."
    ),
    "D": (
        "B + метрико-римові приклади. У промпт додаються 2 вірші з "
        "ідентичною комбінацією метр + стопи + схема римування. Структура."
    ),
    "E": (
        "Повна система: feedback + semantic RAG + метрико-римові приклади. "
        "Разом — максимальний контекст для LLM."
    ),
}


# ---------------------------------------------------------------------------
# Insights tuning constants
# ---------------------------------------------------------------------------

# Headline metrics for the insights summary. We avoid surfacing every metric
# to keep the conclusions section readable; analysts who want the full grid
# already get it via the contributions table and the forest plot.
_HEADLINE_METRICS: tuple[tuple[str, str], ...] = (
    ("meter_accuracy", "точність метру"),
    ("rhyme_accuracy", "точність римування"),
    ("num_iterations", "кількість ітерацій"),
)

# Metrics where a *lower* mean-Δ is the desirable outcome (mirror of
# scripts/analyze_contributions.py:LOWER_IS_BETTER_METRICS). The verdict
# logic flips sign for these so a negative Δ is rendered as
# «статистично покращує», not «погіршує».
_LOWER_IS_BETTER_METRICS: frozenset[str] = frozenset({"num_iterations"})

# Configs grouped by whether the feedback loop is enabled. Used by box /
# heatmap analyses to surface the with-feedback ↔ no-feedback contrast,
# which is the primary insight the F/G/H configs exist to provide.
_WITH_FEEDBACK_CONFIGS: frozenset[str] = frozenset({"B", "C", "D", "E"})
_NO_FEEDBACK_CONFIGS: frozenset[str] = frozenset({"A", "F", "G", "H"})

# Per-component pairs (no_feedback_cfg, with_feedback_cfg, label) that
# isolate the feedback effect on each enrichment combination.
_FEEDBACK_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("A", "B", "лише feedback"),
    ("F", "C", "semantic RAG"),
    ("G", "D", "metric examples"),
    ("H", "E", "RAG + metric examples"),
)

# Pairs of (pure-component name, with-feedback-component name) that point
# to the same enrichment with vs without the feedback loop. Used by
# _analyze_forest to render the contrast narrative.
_COMPARISON_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("pure_semantic_rag", "semantic_rag", "Semantic RAG"),
    ("pure_metric_examples", "metric_examples", "Metric examples"),
    ("pure_rag_metric_combined", "rag_metric_combined", "RAG + metric examples"),
)

# `pure_*` components only differ from with-feedback variants on quality
# metrics. `num_iterations` is structurally 0 in any no-feedback config,
# so contrast bullets skip it (the comparison would always show Δ=0 and
# add noise rather than insight).
_CONTRAST_METRIC_KEYS: frozenset[str] = frozenset({
    "meter_accuracy", "rhyme_accuracy", "semantic_relevance",
})

# Component names that belong to the "with-feedback" comparison family
# vs the "pure / no-feedback" family. Used by the headline split.
_WITH_FEEDBACK_COMPONENTS: frozenset[str] = frozenset({
    "feedback_loop", "semantic_rag", "metric_examples",
    "rag_metric_combined", "feedback_value_full",
})
_PURE_COMPONENTS: frozenset[str] = frozenset({
    "pure_semantic_rag", "pure_metric_examples", "pure_rag_metric_combined",
})

# How wide the IQR has to be before we tag a config as "noisy" — narrower
# than ~10pp accuracy means the LLM behaviour is consistent enough to
# attribute differences to the configuration rather than to randomness.
_NOISY_IQR_THRESHOLD = 0.10
# Heatmap "weak cells" cutoff: cells with mean meter_accuracy below this
# are surfaced as the worst pain points in the per-plot analysis.
_WEAK_CELL_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BatchArtifacts:
    """Everything the ablation dashboard needs for a single batch.

    Built by :func:`build_artifacts` once per request and consumed by
    both the HTML template (`ablation_report.html`) and the JSON API
    schema (`AblationReportResponseSchema`).
    """

    batch_id: str
    metadata: dict[str, object]
    contributions: list[dict[str, object]]
    contributions_by_cat: list[dict[str, object]]
    plot_urls: dict[str, str]
    components: list[ComponentExplanation] = field(default_factory=list)
    plot_explanations: dict[str, PlotExplanation] = field(default_factory=dict)
    plot_analyses: dict[str, PlotAnalysis] = field(default_factory=dict)
    scenarios_by_category: list[dict[str, object]] = field(default_factory=list)
    configs: list[dict[str, object]] = field(default_factory=list)
    insights: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_artifacts(
    results_dir: Path,
    registry: IScenarioRegistry,
) -> BatchArtifacts | None:
    """Find the most recent `batch_*/` folder under ``results_dir`` and
    assemble a :class:`BatchArtifacts` from its files.

    Returns ``None`` when no qualifying batch folder exists (the route
    decides whether to render an empty page or return 404).
    """
    if not results_dir.exists():
        return None
    candidates = sorted(
        (d for d in results_dir.glob("batch_*") if (d / "report.json").is_file()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None
    batch_dir = candidates[0]
    metadata = _read_json(batch_dir / "report.json")
    contributions = _read_csv(batch_dir / "contributions.csv")
    by_cat = _read_csv(batch_dir / "contributions_by_cat.csv")
    runs = _load_runs(batch_dir / "runs.csv")
    plots = _plot_urls(batch_dir, metadata)
    return BatchArtifacts(
        batch_id=batch_dir.name,
        metadata=metadata,
        contributions=contributions,
        contributions_by_cat=by_cat,
        plot_urls=plots,
        components=list(COMPONENT_GLOSSARY),
        plot_explanations=dict(PLOT_GLOSSARY),
        plot_analyses={
            "forest": _analyze_forest(contributions),
            "box": _analyze_box(runs),
            "heatmap": _analyze_heatmap(runs),
            "by_category": _analyze_by_category(by_cat),
        },
        scenarios_by_category=_scenarios_by_category(registry),
        configs=_configs(),
        insights=_build_insights(contributions, metadata),
    )


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------

def _load_runs(path: Path) -> list[dict[str, object]]:
    """Stream runs.csv into dicts, dropping rows with non-empty error.

    Failed runs have meaningless metric values (zeros from defaults) so
    they would distort medians and box plots. Returns an empty list when
    the file is missing — every analyzer that consumes it tolerates that
    by reporting "no data".
    """
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            err = (raw.get("error") or "").strip()
            if err:
                continue
            rows.append({
                "scenario_id": raw.get("scenario_id", ""),
                "category": raw.get("category", ""),
                "config_label": raw.get("config_label", ""),
                "seed": int(raw.get("seed") or 0),
                "meter_accuracy": _as_float(raw.get("meter_accuracy")),
                "rhyme_accuracy": _as_float(raw.get("rhyme_accuracy")),
                "num_iterations": _as_float(raw.get("num_iterations")),
            })
    return rows


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _read_csv(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        for raw in csv.DictReader(f):
            rows.append(_coerce_row(raw))
    return rows


def _coerce_row(raw: dict[str, str]) -> dict[str, object]:
    """Parse numeric columns so the template can format them without string math."""
    out: dict[str, object] = dict(raw)
    for num_key in ("n",):
        raw_val = raw.get(num_key, "")
        if raw_val:
            with contextlib.suppress(TypeError, ValueError):
                out[num_key] = int(raw_val)
    for num_key in ("mean_delta", "ci_low", "ci_high", "p_value"):
        raw_val = raw.get(num_key, "")
        if raw_val:
            with contextlib.suppress(TypeError, ValueError):
                out[num_key] = float(raw_val)
    if "significant" in raw:
        out["significant"] = raw["significant"].strip().lower() == "true"
    return out


def _plot_urls(batch_dir: Path, metadata: dict[str, object]) -> dict[str, str]:
    """Build /results/<batch>/plots/*.png URLs (served by StaticFiles mount).

    Prefers paths listed in report.json["plots"]; falls back to the standard
    filenames so the page still shows something if report.json is incomplete.
    """
    base = f"/results/{batch_dir.name}"
    declared = metadata.get("plots")
    if isinstance(declared, dict):
        return {k: f"{base}/{v}" for k, v in declared.items() if isinstance(v, str)}
    return {
        "forest": f"{base}/plots/forest.png",
        "box": f"{base}/plots/box_by_config.png",
        "heatmap": f"{base}/plots/heatmap.png",
        "by_category": f"{base}/plots/contribution_by_cat.png",
    }


# ---------------------------------------------------------------------------
# Catalogues
# ---------------------------------------------------------------------------

def _scenarios_by_category(
    registry: IScenarioRegistry,
) -> list[dict[str, object]]:
    """Group registered scenarios by category for template rendering."""
    grouped: dict[ScenarioCategory, list[dict[str, object]]] = {
        cat: [] for cat in _CATEGORY_LABELS
    }
    for s in registry.all:
        grouped[s.category].append({
            "id": s.id,
            "name": s.name,
            "theme": s.theme,
            "meter": s.meter,
            "foot_count": s.foot_count,
            "rhyme_scheme": s.rhyme_scheme,
            "description": s.description,
            "expected_to_succeed": s.expected_to_succeed,
        })
    return [
        {
            "category_id": cat.value,
            "category_label": _CATEGORY_LABELS[cat],
            "category_blurb": _CATEGORY_BLURB[cat],
            "scenarios": grouped[cat],
        }
        for cat in _CATEGORY_LABELS
        if grouped[cat]
    ]


def _configs() -> list[dict[str, object]]:
    """Return all ablation configs with human-friendly descriptions."""
    return [
        {
            "label": c.label,
            "short_description": c.description,
            "long_description": _CONFIG_HUMAN_DESC.get(c.label, c.description),
            "enabled_stages": sorted(c.enabled_stages),
        }
        for c in ABLATION_CONFIGS
    ]


# ---------------------------------------------------------------------------
# Insights & per-plot analyses
# ---------------------------------------------------------------------------

def _build_insights(
    contributions: list[dict[str, object]],
    metadata: dict[str, object],
) -> dict[str, object]:
    """Derive a short narrative summary from the paired-Δ table.

    Returns a dict with two lists:
      - ``component_lines`` — one bullet per (component, metric)
        pair on the headline metrics, with sign + significance.
      - ``cost_lines`` — bullets summarising token + cost totals.
    Plus a top-level ``headline`` sentence describing the most useful
    component overall (largest positive Δ across headline metrics with a
    non-zero CI).
    """
    component_lines: list[dict[str, str]] = []
    # Track best effects in two separate buckets so users see *both* the
    # winner among with-feedback comparisons (=converged quality) and
    # among pure / no-feedback comparisons (=raw first-draft quality).
    best_converged: tuple[str, str, float] | None = None
    best_raw: tuple[str, str, float] | None = None

    for metric_key, metric_label in _HEADLINE_METRICS:
        for row in contributions:
            if row.get("metric") != metric_key:
                continue
            comp = str(row.get("component", ""))
            mean = _as_float(row.get("mean_delta"))
            ci_low = _as_float(row.get("ci_low"))
            ci_high = _as_float(row.get("ci_high"))
            sig = bool(row.get("significant", False))
            verdict, tone = _verdict_for(mean, sig, metric_key)
            component_lines.append({
                "component": comp,
                "metric_key": metric_key,
                "metric_label": metric_label,
                "mean": f"{mean:+.3f}",
                "ci": f"[{ci_low:+.3f}, {ci_high:+.3f}]",
                "verdict": verdict,
                "tone": tone,
            })
            # Track the largest "good" effect: positive Δ for normal
            # metrics, negative Δ for lower-is-better metrics. Rank by
            # magnitude in the right direction; keep the signed mean for
            # the headline so num_iterations shows up as «-0.5» (fewer
            # iterations) rather than a misleading «+0.5».
            is_good = (
                (mean < 0) if metric_key in _LOWER_IS_BETTER_METRICS
                else (mean > 0)
            )
            if sig and is_good:
                candidate = (comp, metric_label, mean)
                if comp in _PURE_COMPONENTS:
                    if best_raw is None or abs(mean) > abs(best_raw[2]):
                        best_raw = candidate
                else:
                    if best_converged is None or abs(mean) > abs(best_converged[2]):
                        best_converged = candidate

    cost = metadata.get("cost") if isinstance(metadata, dict) else None
    cost_lines: list[str] = []
    if isinstance(cost, dict) and cost.get("total_tokens"):
        total_cost = _as_float(cost.get("total_cost_usd"))
        total_tokens = int(_as_float(cost.get("total_tokens")))
        avg_cost = _as_float(cost.get("avg_cost_per_run_usd"))
        cost_lines.append(
            f"Сумарно витрачено ${total_cost:.4f} на {total_tokens:,} "
            f"токенів за весь батч.",
        )
        cost_lines.append(
            f"У середньому ${avg_cost:.4f} на одну згенеровану клітинку.",
        )
        per_config = cost.get("per_config")
        if isinstance(per_config, list) and per_config:
            most_exp = max(
                per_config,
                key=lambda r: _as_float(r.get("avg_cost_per_run_usd"))
                              if isinstance(r, dict) else 0.0,
            )
            if isinstance(most_exp, dict):
                cost_lines.append(
                    f"Найдорожчий конфіг — {most_exp.get('config')} "
                    f"(${_as_float(most_exp.get('avg_cost_per_run_usd')):.4f} / прогін).",
                )
            # Feedback overhead: average $ cost difference between each
            # (no_feedback, with_feedback) pair. Tells the operator how
            # much the feedback loop actually costs at the wallet level
            # — a useful trade-off lens against the accuracy-Δ headline.
            cost_by_cfg = {
                str(r.get("config")): _as_float(r.get("avg_cost_per_run_usd"))
                for r in per_config if isinstance(r, dict)
            }
            gaps: list[float] = []
            for nf, wf, _name in _FEEDBACK_PAIRS:
                if nf in cost_by_cfg and wf in cost_by_cfg:
                    gap = cost_by_cfg[wf] - cost_by_cfg[nf]
                    if gap > 0:
                        gaps.append(gap)
            if gaps:
                avg_overhead = sum(gaps) / len(gaps)
                cost_lines.append(
                    f"Feedback-цикл коштує в середньому "
                    f"+${avg_overhead:.4f} на прогін (середня різниця "
                    f"між парами {', '.join(f'{wf}-{nf}' for nf, wf, _ in _FEEDBACK_PAIRS)}). "
                    f"Зважуйте проти Δ-метрик нижче, щоб вирішити, "
                    f"чи feedback виправдовує свою вартість.",
                )

    headline_parts: list[str] = []
    if best_converged is not None:
        headline_parts.append(
            f"за фінальною якістю — {best_converged[0]} "
            f"(Δ {best_converged[2]:+.3f} на {best_converged[1]})"
        )
    if best_raw is not None:
        headline_parts.append(
            f"за raw-якістю першого драфту — {best_raw[0]} "
            f"(Δ {best_raw[2]:+.3f} на {best_raw[1]})"
        )

    if headline_parts:
        headline = "Найкорисніший компонент: " + "; ".join(headline_parts) + "."
    else:
        headline = (
            "Жоден компонент не показав статистично значущого позитивного "
            "впливу на основні метрики. Можливі причини: замало seed'ів, "
            "сильна дисперсія LLM, або компоненти справді не працюють "
            "на цьому корпусі сценаріїв."
        )

    return {
        "headline": headline,
        "component_lines": component_lines,
        "cost_lines": cost_lines,
    }


def _verdict_for(mean: float, significant: bool, metric: str = "") -> tuple[str, str]:
    """Return (verdict_text, css_tone) for an insight bullet.

    For ``LOWER_IS_BETTER`` metrics (e.g. num_iterations) the sign of
    "good" is inverted: a negative mean-Δ means the component drove the
    value down, which is the desired outcome.
    """
    if not significant:
        return ("ефект непостійний (CI перетинає 0)", "neutral")
    is_good = (mean < 0) if metric in _LOWER_IS_BETTER_METRICS else (mean > 0)
    if is_good:
        return ("статистично покращує", "positive")
    return ("статистично погіршує", "negative")


def _as_float(value: object, default: float = 0.0) -> float:
    """Best-effort numeric coercion for loosely-typed CSV/JSON dict values.

    The contributions/metadata dicts come from stdlib csv/json with values
    typed ``object``. Centralising the int/float/str-or-None coercion here
    keeps the insights builder readable and lets mypy verify the result.
    """
    if value is None or value == "":
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _empty_analysis(reason: str) -> PlotAnalysis:
    return PlotAnalysis(summary=reason, bullets=[], empty=True)


def _analyze_forest(contributions: list[dict[str, object]]) -> PlotAnalysis:
    """Group components by tone for the forest plot."""
    if not contributions:
        return _empty_analysis(
            "Дані відсутні — графік нічого не показує.",
        )

    # Surface only the headline metrics so the commentary stays focused on
    # the same dimensions the box / heatmap plots are drawn on.
    headline_keys = {key for key, _ in _HEADLINE_METRICS}
    headline_label = dict(_HEADLINE_METRICS)
    pos: list[str] = []
    neg: list[str] = []
    inconclusive: list[str] = []
    for row in contributions:
        metric = str(row.get("metric", ""))
        if metric not in headline_keys:
            continue
        comp = str(row.get("component", ""))
        mean = _as_float(row.get("mean_delta"))
        sig = bool(row.get("significant", False))
        label = f"{comp} (Δ {mean:+.3f} на {headline_label[metric]})"
        is_good = (
            (mean < 0) if metric in _LOWER_IS_BETTER_METRICS else (mean > 0)
        )
        if sig and is_good:
            pos.append(label)
        elif sig and mean != 0:
            neg.append(label)
        else:
            inconclusive.append(label)

    bullets: list[str] = []
    if pos:
        bullets.append("✅ Статистично покращують: " + "; ".join(pos) + ".")
    if neg:
        bullets.append("❌ Статистично погіршують: " + "; ".join(neg) + ".")
    if inconclusive:
        bullets.append(
            "⚪ Ефект непостійний (CI перетинає 0): "
            + "; ".join(inconclusive) + ".",
        )

    # Contrast: how does feedback change the raw effect of each
    # enrichment? Compare paired (pure_X, X) Δ-values on accuracy
    # metrics. Only show meaningful magnitudes (|Δ| ≥ 0.01) to avoid
    # noise on near-zero pairs.
    contrib_idx: dict[tuple[str, str], float] = {
        (str(r.get("metric", "")), str(r.get("component", ""))):
            _as_float(r.get("mean_delta"))
        for r in contributions
    }
    contrast_bullets: list[str] = []
    for metric_key in (k for k, _ in _HEADLINE_METRICS if k in _CONTRAST_METRIC_KEYS):
        for pure, withfb, label in _COMPARISON_PAIRS:
            d_pure = contrib_idx.get((metric_key, pure))
            d_with = contrib_idx.get((metric_key, withfb))
            if d_pure is None or d_with is None:
                continue
            if max(abs(d_pure), abs(d_with)) < 0.01:
                continue
            # Narrative based on magnitude relationship.
            if abs(d_pure) > abs(d_with) * 1.2:
                narr = "feedback частково *маскує* raw-ефект (без нього вплив сильніший)"
            elif abs(d_with) > abs(d_pure) * 1.2:
                narr = "ефективний переважно *в парі з feedback* (один без іншого слабший)"
            else:
                narr = "стабільний ефект *незалежно* від feedback"
            contrast_bullets.append(
                f"{label} на {headline_label[metric_key]}: "
                f"з feedback Δ {d_with:+.3f}, без — Δ {d_pure:+.3f} → {narr}.",
            )
    if contrast_bullets:
        bullets.append(
            "🔍 Контраст «з feedback ↔ без feedback» — головна цінність "
            "конфігів F/G/H:",
        )
        bullets.extend(f"   • {b}" for b in contrast_bullets)

    if pos:
        summary = (
            f"З {len(pos) + len(neg) + len(inconclusive)} перевірених "
            f"внесків {len(pos)} мають доведений позитивний ефект, "
            f"{len(neg)} — негативний, {len(inconclusive)} — у межах шуму."
        )
        bullets.append(
            "Висновок: компоненти з доведеним ефектом варто залишати "
            "в pipeline; компоненти без значущого Δ можна вимикати "
            "для економії токенів — їхня користь не доведена.",
        )
    elif neg:
        summary = (
            "Жоден компонент не покращив метрики статистично значуще, "
            f"проте {len(neg)} компонент(ів) їх погіршив(ли)."
        )
        bullets.append(
            "Висновок: налаштування або корпус потребують перегляду — "
            "поточні налаштування активно шкодять. Перевірте якість "
            "RAG-корпусу та якість фідбеку.",
        )
    else:
        summary = (
            "Усі ефекти лежать у межах шуму — жоден компонент не "
            "довів свою користь чи шкоду на цьому масштабі прогонів."
        )
        bullets.append(
            "Висновок: збільште кількість seeds (більше повторень "
            "пом'якшать LLM-стохастичність) або перевірте, чи дійсно "
            "сценарії «складні» — може, на легких задачах baseline "
            "вже близький до стелі.",
        )

    return PlotAnalysis(summary=summary, bullets=bullets)


def _analyze_box(runs: list[dict[str, object]]) -> PlotAnalysis:
    """Per-config median + IQR; flag stable vs noisy configs."""
    if not runs:
        return _empty_analysis(
            "Файл runs.csv не знайдено — розподіл побудувати ні з чого.",
        )

    grouped: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        cfg = str(r.get("config_label", ""))
        if cfg:
            grouped[cfg].append(_as_float(r.get("meter_accuracy")))

    if not grouped:
        return _empty_analysis("У runs.csv не знайдено валідних рядків.")

    stats_per_cfg: list[tuple[str, float, float, float, float]] = []
    for cfg, vals in sorted(grouped.items()):
        if len(vals) < 2:
            stats_per_cfg.append((cfg, vals[0], vals[0], vals[0], 0.0))
            continue
        median = statistics.median(vals)
        try:
            q1, _q2, q3 = statistics.quantiles(vals, n=4)
        except statistics.StatisticsError:
            q1, q3 = min(vals), max(vals)
        stats_per_cfg.append((cfg, median, q1, q3, q3 - q1))

    bullets: list[str] = []
    for cfg, med, q1, q3, iqr in stats_per_cfg:
        bullets.append(
            f"Конфіг <code>{cfg}</code>: медіана {med:.2f}, "
            f"IQR [{q1:.2f}; {q3:.2f}] (ширина {iqr:.2f}).",
        )

    best_cfg = max(stats_per_cfg, key=lambda x: x[1])
    worst_cfg = min(stats_per_cfg, key=lambda x: x[1])
    most_stable = min(stats_per_cfg, key=lambda x: x[4])
    most_noisy = max(stats_per_cfg, key=lambda x: x[4])

    bullets.append(
        f"Найвища медіана meter_accuracy — у <code>{best_cfg[0]}</code> "
        f"({best_cfg[1]:.2f}); найнижча — у <code>{worst_cfg[0]}</code> "
        f"({worst_cfg[1]:.2f}).",
    )
    if most_noisy[4] > _NOISY_IQR_THRESHOLD:
        bullets.append(
            f"Найшумніший конфіг — <code>{most_noisy[0]}</code> "
            f"(IQR {most_noisy[4]:.2f}); найстабільніший — "
            f"<code>{most_stable[0]}</code> (IQR {most_stable[4]:.2f}).",
        )

    # ── With-feedback ↔ no-feedback cluster contrast ──────────────────
    med_by_cfg = {cfg: med for cfg, med, *_ in stats_per_cfg}
    wf_meds = [med_by_cfg[c] for c in _WITH_FEEDBACK_CONFIGS if c in med_by_cfg]
    nf_meds = [med_by_cfg[c] for c in _NO_FEEDBACK_CONFIGS if c in med_by_cfg]
    if wf_meds and nf_meds:
        wf_avg = sum(wf_meds) / len(wf_meds)
        nf_avg = sum(nf_meds) / len(nf_meds)
        wf_list = ", ".join(sorted(c for c in _WITH_FEEDBACK_CONFIGS if c in med_by_cfg))
        nf_list = ", ".join(sorted(c for c in _NO_FEEDBACK_CONFIGS if c in med_by_cfg))
        bullets.append(
            f"📊 Кластер <b>з feedback</b> ({wf_list}): середня медіана "
            f"{wf_avg:.2f}; <b>без feedback</b> ({nf_list}): {nf_avg:.2f}. "
            f"Сумарний зсув від feedback на сирому розподілі: "
            f"{wf_avg - nf_avg:+.2f}.",
        )

    pair_lines: list[str] = []
    for nf, wf, name in _FEEDBACK_PAIRS:
        if nf in med_by_cfg and wf in med_by_cfg:
            gap = med_by_cfg[wf] - med_by_cfg[nf]
            pair_lines.append(
                f"<code>{wf}</code>−<code>{nf}</code> ({name}): {gap:+.2f}",
            )
    if pair_lines:
        bullets.append(
            "Розрив feedback-vs-no-feedback по парах однакових збагачень: "
            + "; ".join(pair_lines)
            + ". Велика різниця → feedback робить основну роботу для цього "
              "поєднання; мала → збагачення вже самотужки дає якість.",
        )

    bullets.append(
        "Висновок: різниця медіан між конфігами — це сирий «зсув якості»; "
        "сама лише різниця ще не є статистично значущою — для висновків "
        "про значущість дивіться forest plot вище.",
    )

    summary = (
        f"Найкраща середня medтан-якість у <code>{best_cfg[0]}</code> "
        f"({best_cfg[1]:.2f}), найгірша — у <code>{worst_cfg[0]}</code> "
        f"({worst_cfg[1]:.2f}); різниця {best_cfg[1] - worst_cfg[1]:+.2f}."
    )
    return PlotAnalysis(summary=summary, bullets=bullets)


def _analyze_heatmap(runs: list[dict[str, object]]) -> PlotAnalysis:
    """Find weakest cells + best/worst configs from the heatmap matrix."""
    if not runs:
        return _empty_analysis(
            "Файл runs.csv не знайдено — heatmap нічого аналізувати.",
        )

    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_cfg: dict[str, list[float]] = defaultdict(list)
    by_scen: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        cfg = str(r.get("config_label", ""))
        sid = str(r.get("scenario_id", ""))
        val = _as_float(r.get("meter_accuracy"))
        cells[(cfg, sid)].append(val)
        by_cfg[cfg].append(val)
        by_scen[sid].append(val)

    if not cells:
        return _empty_analysis("У runs.csv не знайдено валідних рядків.")

    # Mean meter_accuracy per (config, scenario) cell.
    cell_means = {k: statistics.fmean(v) for k, v in cells.items()}
    best_cfg = max(by_cfg.items(), key=lambda kv: statistics.fmean(kv[1]))
    worst_scen = min(by_scen.items(), key=lambda kv: statistics.fmean(kv[1]))

    bullets: list[str] = []
    bullets.append(
        f"Найкращий конфіг за середньою якістю по всіх сценаріях — "
        f"<code>{best_cfg[0]}</code> ({statistics.fmean(best_cfg[1]):.2f}).",
    )
    bullets.append(
        f"Найскладніший сценарій (найнижча середня по конфігах) — "
        f"<code>{worst_scen[0]}</code> "
        f"({statistics.fmean(worst_scen[1]):.2f}).",
    )
    # Take all weak cells (not just top-3) so we can split them by group.
    all_weak = sorted(
        [(cell, mean) for cell, mean in cell_means.items()
         if mean < _WEAK_CELL_THRESHOLD],
        key=lambda kv: kv[1],
    )
    # Split: cells in with-feedback configs are *real* failure modes;
    # cells in no-feedback configs are largely expected (no feedback to
    # repair the initial draft) — surfacing them as separate groups
    # avoids treating "F bad on N09" as a system problem.
    weak_with_feedback = [
        (cell, mean) for cell, mean in all_weak
        if cell[0] in _WITH_FEEDBACK_CONFIGS
    ]
    weak_no_feedback = [
        (cell, mean) for cell, mean in all_weak
        if cell[0] in _NO_FEEDBACK_CONFIGS
    ]

    if weak_with_feedback:
        listed = "; ".join(
            f"<code>{cfg}×{sid}</code> ({mean:.2f})"
            for (cfg, sid), mean in weak_with_feedback[:3]
        )
        bullets.append(
            f"🔴 Слабкі клітинки <b>серед конфігів з feedback</b> "
            f"(нижче {_WEAK_CELL_THRESHOLD:.0%}): {listed}. "
            f"Це <b>справжні</b> failure modes — навіть повний цикл "
            f"виправлень не дає прийнятної якості.",
        )
    elif all_weak:
        bullets.append(
            f"✅ Серед конфігів з feedback (B-E) <b>немає</b> клітинок "
            f"нижче {_WEAK_CELL_THRESHOLD:.0%} — повний цикл виправлень "
            f"справляється з усіма сценаріями.",
        )

    if weak_no_feedback:
        listed = "; ".join(
            f"<code>{cfg}×{sid}</code> ({mean:.2f})"
            for (cfg, sid), mean in weak_no_feedback[:3]
        )
        bullets.append(
            f"🟡 Слабкі клітинки <b>лише серед конфігів без feedback</b> "
            f"(F-H): {listed}. Це очікувано: без feedback-репарації "
            f"перший драфт часто не дотягує. Цікавим є саме <b>розрив</b> "
            f"між цими клітинками і їхніми feedback-парами (E vs H тощо) — "
            f"показує, наскільки feedback закриває розрив.",
        )

    bullets.append(
        "Висновок: червоні стовпці серед {B,C,D,E} = «гарячі точки» для "
        "наступної ітерації pipeline'у. Червоні серед {F,G,H} — норма "
        "(феномен «без feedback нема репарації»), важлива інформація лише "
        "коли вони збігаються з аналогічно-червоними клітинками в "
        "feedback-парах.",
    )

    summary = (
        f"Найкраща конфігурація — <code>{best_cfg[0]}</code>; "
        f"найскладніший сценарій — <code>{worst_scen[0]}</code>. "
        f"Справжніх failure-точок з feedback: {len(weak_with_feedback)}; "
        f"очікувано-слабких без feedback: {len(weak_no_feedback)}."
    )
    return PlotAnalysis(summary=summary, bullets=bullets)


def _analyze_by_category(by_cat: list[dict[str, object]]) -> PlotAnalysis:
    """Per-category strongest helping component on headline metrics."""
    if not by_cat:
        return _empty_analysis(
            "Файл contributions_by_cat.csv не знайдено або порожній.",
        )

    headline_keys = {key for key, _ in _HEADLINE_METRICS}
    by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in by_cat:
        if str(row.get("metric", "")) in headline_keys:
            by_category[str(row.get("category", ""))].append(row)

    if not by_category:
        return _empty_analysis(
            "Розбиття по категоріях не містить headline-метрик "
            "(meter / rhyme accuracy).",
        )

    bullets: list[str] = []
    for cat in sorted(by_category):
        rows = by_category[cat]
        sig_pos = [r for r in rows if r.get("significant") and _as_float(r.get("mean_delta")) > 0]
        if sig_pos:
            best = max(sig_pos, key=lambda r: _as_float(r.get("mean_delta")))
            bullets.append(
                f"Категорія <b>{cat}</b>: найкорисніший компонент — "
                f"<code>{best.get('component')}</code> "
                f"(Δ {_as_float(best.get('mean_delta')):+.3f}).",
            )
        else:
            bullets.append(
                f"Категорія <b>{cat}</b>: жоден компонент не показав "
                f"статистично значущого позитивного ефекту.",
            )

    bullets.append(
        "Висновок: якщо компонент допомагає на одній категорії і нічого "
        "не дає на іншій — це нормально. Edge/corner — там, де є куди "
        "рости; на normal baseline зазвичай уже близький до стелі.",
    )

    summary = (
        f"Розбиття за {len(by_category)} категоріями показує, де саме "
        f"кожен компонент справді працює, а де він зайвий."
    )
    return PlotAnalysis(summary=summary, bullets=bullets)
