"""Concrete evaluation scenario instances — application-level test data.

These are research/evaluation presets, not domain concepts. The domain
defines `EvaluationScenario` (the type) and `ScenarioRegistry` (the
collection); this module defines the specific N01–N05, E01–E05, C01–C08
instances used by the evaluation harness.
"""
from __future__ import annotations

from src.domain.scenarios import EvaluationScenario, ScenarioRegistry
from src.domain.values import ScenarioCategory

NORMAL_SCENARIOS: tuple[EvaluationScenario, ...] = (
    EvaluationScenario(
        id="N01", name="Весна в лісі (ямб, 4 стопи, ABAB)", category=ScenarioCategory.NORMAL,
        theme="весна у лісі, пробудження природи",
        meter="ямб", foot_count=4, rhyme_scheme="ABAB",
        description="Classic 4-foot iamb with cross rhyme — the most common Ukrainian verse form.",
        tags=("nature", "iamb", "cross-rhyme"),
    ),
    EvaluationScenario(
        id="N02", name="Кохання (хорей, 4 стопи, AABB)", category=ScenarioCategory.NORMAL,
        theme="кохання і розлука, сум за коханою людиною",
        meter="хорей", foot_count=4, rhyme_scheme="AABB",
        description="Trochee with paired rhyme — common in folk-style love poetry.",
        tags=("love", "trochee", "paired-rhyme"),
    ),
    EvaluationScenario(
        id="N03", name="Батьківщина (дактиль, 4 стопи, ABBA)", category=ScenarioCategory.NORMAL,
        theme="рідна земля, Україна, патріотизм",
        meter="дактиль", foot_count=4, rhyme_scheme="ABBA",
        description="4-foot dactyl with enclosing rhyme — patriotic verse in a ternary metre.",
        tags=("patriotic", "dactyl", "enclosing-rhyme"),
    ),
    EvaluationScenario(
        id="N04", name="Самотність (амфібрахій, 4 стопи, ABAB)", category=ScenarioCategory.NORMAL,
        theme="самотність, тиша порожньої кімнати",
        meter="амфібрахій", foot_count=4, rhyme_scheme="ABAB",
        stanza_count=2,
        description="Amphibrach with cross rhyme — melancholic, meditative rhythm.",
        tags=("loneliness", "amphibrach", "cross-rhyme"),
    ),
    EvaluationScenario(
        id="N05", name="Місто вночі (анапест, 4 стопи, AABB)", category=ScenarioCategory.NORMAL,
        theme="нічне місто, вогні, відчуження серед натовпу",
        meter="анапест", foot_count=4, rhyme_scheme="AABB",
        stanza_count=2,
        description="Anapest with paired rhyme — modern urban theme.",
        tags=("urban", "anapest", "paired-rhyme"),
    ),
)

EDGE_SCENARIOS: tuple[EvaluationScenario, ...] = (
    EvaluationScenario(
        id="E01", name="Мінімальний розмір (ямб, 2 стопи, ААВВ)", category=ScenarioCategory.EDGE,
        theme="роса на траві",
        meter="ямб", foot_count=2, rhyme_scheme="AABB",
        description="2-foot iamb — very short lines; tests that validator accepts minimal length.",
        tags=("minimal", "iamb", "short-lines"),
    ),
    EvaluationScenario(
        id="E02", name="Великий розмір (ямб, 6 стоп, АВАВ)", category=ScenarioCategory.EDGE,
        theme="історія України від давнини до сьогодення",
        meter="ямб", foot_count=6, rhyme_scheme="ABAB",
        description="6-foot iamb (alexandrine) — long lines; tests pattern generation for high foot count.",
        tags=("long-lines", "iamb", "alexandrine"),
    ),
    EvaluationScenario(
        id="E03", name="Великий розмір (анапест, 6 стоп, ABBA)", category=ScenarioCategory.EDGE,
        theme="морська буря, хвилі, шторм",
        meter="анапест", foot_count=6, rhyme_scheme="ABBA",
        description="Anapest with enclosing rhyme — less common meter, tests correct ternary pattern.",
        tags=("sea", "anapest", "enclosing-rhyme"),
    ),
    EvaluationScenario(
        id="E04", name="Монорима (амфібрахій, 5 стоп, AAAA)", category=ScenarioCategory.EDGE,
        theme="дощ, нескінченний дощ за вікном",
        meter="амфібрахій", foot_count=5, rhyme_scheme="AAAA",
        description="All four lines must rhyme — hardest rhyme constraint for the validator.",
        tags=("monorhyme", "amphibrach", "rain"),
    ),
    EvaluationScenario(
        id="E05", name="Абстрактна тема (дактиль, 5 стоп, ABAB)", category=ScenarioCategory.EDGE,
        theme="час як безкінечна спіраль",
        meter="дактиль", foot_count=5, rhyme_scheme="ABAB",
        description="Abstract philosophical theme — tests retrieval with no close corpus match.",
        tags=("abstract", "dactyl", "philosophy"),
    ),
)

CORNER_SCENARIOS: tuple[EvaluationScenario, ...] = (
    EvaluationScenario(
        id="C01", name="Мінімальна тема (хорей, 6 стоп, ABAB)", category=ScenarioCategory.CORNER,
        theme="тиша",
        meter="хорей", foot_count=6, rhyme_scheme="ABAB",
        description="Minimal single-word theme — pipeline must handle gracefully.",
        tags=("minimal-input", "robustness"),
        expected_to_succeed=True,
    ),
    EvaluationScenario(
        id="C02", name="Дуже довга тема (ямб, 5 стоп, ABAB)", category=ScenarioCategory.CORNER,
        theme=(
            "Написати вірш про те, як вранці сонце встає над полями пшениці, "
            "і селяни йдуть на роботу, і діти біжать до школи, "
            "і старий дідусь сидить на лавці біля хати і згадує молодість, "
            "коли він теж бігав по полях і співав пісні, "
            "а тепер тільки спогади залишились"
        ),
        meter="ямб", foot_count=5, rhyme_scheme="ABAB",
        description="Very long theme (>200 chars) — tests prompt truncation / retrieval robustness.",
        tags=("long-input", "robustness"),
        expected_to_succeed=True,
    ),
    EvaluationScenario(
        id="C03", name="Тема латиницею (дактиль, 3 стопи, ABAB)", category=ScenarioCategory.CORNER,
        theme="spring in the forest, birds singing",
        meter="дактиль", foot_count=3, rhyme_scheme="ABAB",
        description="Theme in English (Latin script) — tests retrieval with language mismatch.",
        tags=("language-mismatch", "robustness"),
        expected_to_succeed=True,
    ),
    EvaluationScenario(
        id="C04", name="Невідомий метр (гекзаметр, 4 стопи, ABAB)", category=ScenarioCategory.CORNER,
        theme="зимовий ліс",
        meter="гекзаметр", foot_count=4, rhyme_scheme="ABAB",
        description="Unsupported meter name — pipeline should fallback or report clearly.",
        tags=("unsupported-meter", "robustness"),
        expected_to_succeed=False,
    ),
    EvaluationScenario(
        id="C05", name="Один рядок (анапест, 1 стопа, ABAB)", category=ScenarioCategory.CORNER,
        theme="мить",
        meter="анапест", foot_count=1, rhyme_scheme="ABAB",
        description="1-foot anapest — single stressed syllable per line, extreme minimal.",
        tags=("extreme-minimal", "robustness"),
        expected_to_succeed=True,
    ),
    EvaluationScenario(
        id="C06", name="Спецсимволи в темі (амфібрахій, 6 стоп, AABB)", category=ScenarioCategory.CORNER,
        theme="весна!!! @#$% <script>alert('xss')</script> & природа 🌸",
        meter="амфібрахій", foot_count=6, rhyme_scheme="AABB",
        description="Special characters, HTML, emoji in theme — tests input sanitization.",
        tags=("injection", "robustness"),
        expected_to_succeed=True,
    ),
    EvaluationScenario(
        id="C07", name="Змішана тема (укр + рус) (ямб, 4 стопи, ABAB)", category=ScenarioCategory.CORNER,
        theme="весна красивая, цвіти розпускаються",
        meter="ямб", foot_count=4, rhyme_scheme="ABAB",
        description="Mixed Ukrainian/Russian — tests that output stays in Ukrainian.",
        tags=("mixed-language", "robustness"),
        expected_to_succeed=True,
    ),
    EvaluationScenario(
        id="C08", name="Нульова кількість стоп (хорей, 0 стоп, ABAB)", category=ScenarioCategory.CORNER,
        theme="тиша",
        meter="хорей", foot_count=0, rhyme_scheme="ABAB",
        description="foot_count=0 — degenerate input, must not crash.",
        tags=("zero-feet", "robustness"),
        expected_to_succeed=False,
    ),
)

ALL_SCENARIOS: tuple[EvaluationScenario, ...] = (
    NORMAL_SCENARIOS + EDGE_SCENARIOS + CORNER_SCENARIOS
)

SCENARIO_REGISTRY = ScenarioRegistry(ALL_SCENARIOS)


def scenario_by_id(scenario_id: str) -> EvaluationScenario | None:
    """Look up a scenario by ID."""
    return SCENARIO_REGISTRY.by_id(scenario_id)


def scenarios_by_category(category: ScenarioCategory) -> list[EvaluationScenario]:
    """Return all scenarios in a given category."""
    return list(SCENARIO_REGISTRY.by_category(category))
