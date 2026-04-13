"""Evaluation scenarios — types and registry.

Scenario *types* (EvaluationScenario, ScenarioRegistry) live here in the
domain. Concrete scenario *instances* (N01–N05, E01–E05, C01–C08) are
application-level test data and live in
``infrastructure.evaluation.scenario_data``.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from src.domain.errors import UnsupportedConfigError
from src.domain.models import GenerationRequest, MeterSpec, PoemStructure, RhymeScheme
from src.domain.values import ScenarioCategory

# ---------------------------------------------------------------------------
# Scenario value object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvaluationScenario:
    """Single evaluation scenario used by the evaluation matrix.

    Fields:
        id:                Unique scenario identifier, e.g. 'N01'.
        name:              Human-readable name shown in reports.
        category:          normal / edge / corner.
        theme:             Theme string passed to the generator.
        meter:             Meter name (validated via MeterName.parse downstream).
        foot_count:        Number of metrical feet per line.
        rhyme_scheme:      Rhyme scheme pattern (e.g. 'ABAB').
        stanza_count:      Default stanza count if the caller doesn't override.
        lines_per_stanza:  Default lines-per-stanza if the caller doesn't override.
        description:       Free-text description.
        tags:              Arbitrary tuple of tags used for filtering/reporting.
        expected_to_succeed: True for normal/edge scenarios, False for degenerate corner cases.
    """

    id: str
    name: str
    category: ScenarioCategory
    theme: str
    meter: str
    foot_count: int
    rhyme_scheme: str
    stanza_count: int = 1
    lines_per_stanza: int = 4
    description: str = ""
    tags: tuple[str, ...] = ()
    expected_to_succeed: bool = True

    @property
    def total_lines(self) -> int:
        return self.stanza_count * self.lines_per_stanza

    def build_request(
        self,
        stanza_count: int | None = None,
        lines_per_stanza: int | None = None,
    ) -> GenerationRequest:
        """Return a GenerationRequest for this scenario with optional structure overrides."""
        return GenerationRequest(
            theme=self.theme,
            meter=MeterSpec(name=self.meter, foot_count=self.foot_count),
            rhyme=RhymeScheme(pattern=self.rhyme_scheme),
            structure=PoemStructure(
                stanza_count=stanza_count if stanza_count is not None else self.stanza_count,
                lines_per_stanza=(
                    lines_per_stanza if lines_per_stanza is not None else self.lines_per_stanza
                ),
            ),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ScenarioRegistry:
    """Immutable registry of scenarios, queryable by id or category."""

    def __init__(self, scenarios: Iterable[EvaluationScenario]) -> None:
        items = tuple(scenarios)

        ids = [s.id for s in items]
        if len(ids) != len(set(ids)):
            duplicates = sorted({i for i in ids if ids.count(i) > 1})
            raise UnsupportedConfigError(
                f"Duplicate scenario ids in registry: {duplicates}"
            )

        self._items: tuple[EvaluationScenario, ...] = items
        self._by_id: dict[str, EvaluationScenario] = {s.id: s for s in items}

    def __iter__(self) -> Iterator[EvaluationScenario]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def all(self) -> tuple[EvaluationScenario, ...]:
        """Return the full tuple of scenarios in registration order."""
        return self._items

    def by_id(self, scenario_id: str) -> EvaluationScenario | None:
        """Return the scenario with the given id, or None if not found."""
        return self._by_id.get(scenario_id)

    def by_category(self, category: ScenarioCategory) -> tuple[EvaluationScenario, ...]:
        """Return all scenarios matching the given category, in registration order."""
        return tuple(s for s in self._items if s.category == category)


__all__ = [
    "EvaluationScenario",
    "ScenarioRegistry",
]
