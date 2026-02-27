"""Curated evaluation scenarios for automated pipeline testing.

Each scenario defines a complete input request for the poetry generation
system:  theme, meter, rhyme scheme, foot count, and an optional
reference poem for BLEU/ROUGE comparison.

Scenarios are grouped by category:
  - NORMAL:   typical usage with common meters and themes
  - EDGE:     boundary conditions (unusual meters, minimal foot counts)
  - CORNER:   adversarial or degenerate inputs that stress the pipeline
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScenarioCategory(str, Enum):
    NORMAL = "normal"
    EDGE = "edge"
    CORNER = "corner"


@dataclass(frozen=True)
class EvaluationScenario:
    id: str
    name: str
    category: ScenarioCategory
    theme: str
    meter: str
    rhyme_scheme: str
    foot_count: int
    stanza_count: int = 1
    lines_per_stanza: int = 4
    description: str = ""
    reference_poem: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def total_lines(self) -> int:
        return self.stanza_count * self.lines_per_stanza


# ---------------------------------------------------------------------------
# NORMAL scenarios — typical real-world requests
# ---------------------------------------------------------------------------

NORMAL_SCENARIOS: list[EvaluationScenario] = [
    EvaluationScenario(
        id="N01",
        name="Весна в лісі (ямб, ABAB)",
        category=ScenarioCategory.NORMAL,
        theme="весна у лісі, пробудження природи",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        stanza_count=1,
        lines_per_stanza=4,
        description="Classic 4-foot iamb with cross rhyme — the most common Ukrainian verse form.",
        reference_poem=(
            "Весна прийшла у ліс зелений,\n"
            "Де тінь і світло гомонить.\n"
            "Мов сни, пливуть думки натхненні,\n"
            "І серце в тиші гомонить.\n"
        ),
        tags=("nature", "iamb", "cross-rhyme"),
    ),
    EvaluationScenario(
        id="N02",
        name="Кохання (хорей, AABB)",
        category=ScenarioCategory.NORMAL,
        theme="кохання і розлука, сум за коханою людиною",
        meter="хорей",
        rhyme_scheme="AABB",
        foot_count=4,
        stanza_count=1,
        lines_per_stanza=4,
        description="Trochee with paired rhyme — common in folk-style love poetry.",
        reference_poem=(
            "Тихо місяць ніч вітає,\n"
            "Зірка долю провіщає.\n"
            "Серце плаче від розлуки,\n"
            "Тихо падають на руки.\n"
        ),
        tags=("love", "trochee", "paired-rhyme"),
    ),
    EvaluationScenario(
        id="N03",
        name="Батьківщина (ямб, ABBA)",
        category=ScenarioCategory.NORMAL,
        theme="рідна земля, Україна, патріотизм",
        meter="ямб",
        rhyme_scheme="ABBA",
        foot_count=5,
        stanza_count=1,
        lines_per_stanza=4,
        description="5-foot iamb with enclosing rhyme — Shevchenko-style patriotic verse.",
        reference_poem=(
            "Мій рідний краю, ти моя земля,\n"
            "Де колос спілий нахилив колосся.\n"
            "Я чую спів пташиного голосся,\n"
            "І сльози радості збігають з чола.\n"
        ),
        tags=("patriotic", "iamb", "enclosing-rhyme"),
    ),
    EvaluationScenario(
        id="N04",
        name="Самотність (амфібрахій, ABAB)",
        category=ScenarioCategory.NORMAL,
        theme="самотність, тиша порожньої кімнати",
        meter="амфібрахій",
        rhyme_scheme="ABAB",
        foot_count=3,
        stanza_count=2,
        lines_per_stanza=4,
        description="Amphibrach with cross rhyme — melancholic, meditative rhythm.",
        reference_poem=None,
        tags=("loneliness", "amphibrach", "cross-rhyme"),
    ),
    EvaluationScenario(
        id="N05",
        name="Місто вночі (дактиль, AABB)",
        category=ScenarioCategory.NORMAL,
        theme="нічне місто, вогні, відчуження серед натовпу",
        meter="дактиль",
        rhyme_scheme="AABB",
        foot_count=3,
        stanza_count=2,
        lines_per_stanza=4,
        description="Dactyl with paired rhyme — modern urban theme.",
        reference_poem=None,
        tags=("urban", "dactyl", "paired-rhyme"),
    ),
]


# ---------------------------------------------------------------------------
# EDGE scenarios — boundary / uncommon but valid requests
# ---------------------------------------------------------------------------

EDGE_SCENARIOS: list[EvaluationScenario] = [
    EvaluationScenario(
        id="E01",
        name="Мінімальний розмір (ямб, 2 стопи)",
        category=ScenarioCategory.EDGE,
        theme="роса на траві",
        meter="ямб",
        rhyme_scheme="AABB",
        foot_count=2,
        stanza_count=1,
        lines_per_stanza=4,
        description="2-foot iamb — very short lines; tests that validator accepts minimal length.",
        tags=("minimal", "iamb", "short-lines"),
    ),
    EvaluationScenario(
        id="E02",
        name="Великий розмір (ямб, 6 стоп)",
        category=ScenarioCategory.EDGE,
        theme="історія України від давнини до сьогодення",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=6,
        stanza_count=1,
        lines_per_stanza=4,
        description="6-foot iamb (alexandrine) — long lines; tests pattern generation for high foot count.",
        tags=("long-lines", "iamb", "alexandrine"),
    ),
    EvaluationScenario(
        id="E03",
        name="Анапест (ABBA)",
        category=ScenarioCategory.EDGE,
        theme="морська буря, хвилі, шторм",
        meter="анапест",
        rhyme_scheme="ABBA",
        foot_count=3,
        stanza_count=1,
        lines_per_stanza=4,
        description="Anapest with enclosing rhyme — less common meter, tests correct ternary pattern.",
        tags=("sea", "anapest", "enclosing-rhyme"),
    ),
    EvaluationScenario(
        id="E04",
        name="Монорима (AAAA)",
        category=ScenarioCategory.EDGE,
        theme="дощ, нескінченний дощ за вікном",
        meter="хорей",
        rhyme_scheme="AAAA",
        foot_count=4,
        stanza_count=1,
        lines_per_stanza=4,
        description="All four lines must rhyme — hardest rhyme constraint for the validator.",
        tags=("monorhyme", "trochee", "rain"),
    ),
    EvaluationScenario(
        id="E05",
        name="Абстрактна тема (ямб, ABAB)",
        category=ScenarioCategory.EDGE,
        theme="час як безкінечна спіраль",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        stanza_count=1,
        lines_per_stanza=4,
        description="Abstract philosophical theme — tests retrieval with no close corpus match.",
        tags=("abstract", "iamb", "philosophy"),
    ),
]


# ---------------------------------------------------------------------------
# CORNER scenarios — adversarial / degenerate inputs
# ---------------------------------------------------------------------------

CORNER_SCENARIOS: list[EvaluationScenario] = [
    EvaluationScenario(
        id="C01",
        name="Порожня тема",
        category=ScenarioCategory.CORNER,
        theme="",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        description="Empty theme string — pipeline must handle gracefully.",
        tags=("empty-input", "robustness"),
    ),
    EvaluationScenario(
        id="C02",
        name="Дуже довга тема",
        category=ScenarioCategory.CORNER,
        theme=(
            "Написати вірш про те, як вранці сонце встає над полями пшениці, "
            "і селяни йдуть на роботу, і діти біжать до школи, "
            "і старий дідусь сидить на лавці біля хати і згадує молодість, "
            "коли він теж бігав по полях і співав пісні, "
            "а тепер тільки спогади залишились"
        ),
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        description="Very long theme (>200 chars) — tests prompt truncation / retrieval robustness.",
        tags=("long-input", "robustness"),
    ),
    EvaluationScenario(
        id="C03",
        name="Тема латиницею",
        category=ScenarioCategory.CORNER,
        theme="spring in the forest, birds singing",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        description="Theme in English (Latin script) — tests retrieval with language mismatch.",
        tags=("language-mismatch", "robustness"),
    ),
    EvaluationScenario(
        id="C04",
        name="Невідомий метр",
        category=ScenarioCategory.CORNER,
        theme="зимовий ліс",
        meter="гекзаметр",
        rhyme_scheme="ABAB",
        foot_count=4,
        description="Unsupported meter name — pipeline should fallback or report clearly.",
        tags=("unsupported-meter", "robustness"),
    ),
    EvaluationScenario(
        id="C05",
        name="Один рядок (foot_count=1)",
        category=ScenarioCategory.CORNER,
        theme="мить",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=1,
        description="1-foot iamb — single stressed syllable per line, extreme minimal.",
        tags=("extreme-minimal", "robustness"),
    ),
    EvaluationScenario(
        id="C06",
        name="Спецсимволи в темі",
        category=ScenarioCategory.CORNER,
        theme="весна!!! @#$% <script>alert('xss')</script> & природа 🌸",
        meter="хорей",
        rhyme_scheme="AABB",
        foot_count=4,
        description="Special characters, HTML, emoji in theme — tests input sanitization.",
        tags=("injection", "robustness"),
    ),
    EvaluationScenario(
        id="C07",
        name="Змішана тема (укр + рус)",
        category=ScenarioCategory.CORNER,
        theme="весна красивая, цвіти розпускаються",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=4,
        description="Mixed Ukrainian/Russian — tests that output stays in Ukrainian.",
        tags=("mixed-language", "robustness"),
    ),
    EvaluationScenario(
        id="C08",
        name="Нульова кількість стоп",
        category=ScenarioCategory.CORNER,
        theme="тиша",
        meter="ямб",
        rhyme_scheme="ABAB",
        foot_count=0,
        description="foot_count=0 — degenerate input, must not crash.",
        tags=("zero-feet", "robustness"),
    ),
]


# ---------------------------------------------------------------------------
# All scenarios combined
# ---------------------------------------------------------------------------

ALL_SCENARIOS: list[EvaluationScenario] = (
    NORMAL_SCENARIOS + EDGE_SCENARIOS + CORNER_SCENARIOS
)


def scenarios_by_category(category: ScenarioCategory) -> list[EvaluationScenario]:
    return [s for s in ALL_SCENARIOS if s.category == category]


def scenario_by_id(scenario_id: str) -> EvaluationScenario | None:
    for s in ALL_SCENARIOS:
        if s.id == scenario_id:
            return s
    return None
