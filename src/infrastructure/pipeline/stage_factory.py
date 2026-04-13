"""IStageFactory implementation — builds an ordered stage list from registrations.

The composition root registers stages with `StageRegistration` entries;
the factory itself has no hardcoded stage catalogue. Adding a new stage
becomes a single new registration call (and whatever builder you want
at the composition-root level) rather than an edit to a typed dataclass
+ the factory + the skip-policy tables.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.ports import IPipelineStage, IStageFactory


@dataclass(frozen=True)
class StageRegistration:
    """One registered stage with its canonical name and togglability.

    `togglable=True` means the ablation config can turn the stage off
    at runtime via `IStageSkipPolicy.should_skip`. `togglable=False`
    means the stage always runs (prompt construction, generation).
    """

    name: str
    stage: IPipelineStage
    togglable: bool = True


class DefaultStageFactory(IStageFactory):
    """`IStageFactory` backed by an ordered list of `StageRegistration`s.

    The factory returns every registered stage in declaration order; the
    injected `IStageSkipPolicy` handles togglable-stage skipping, so the
    factory does not need its own `enabled_stages` filter.
    """

    def __init__(self, registrations: list[StageRegistration]) -> None:
        self._registrations: tuple[StageRegistration, ...] = tuple(registrations)
        # Duplicate-name check — a registration typo used to manifest as
        # a silent later-wins override.
        seen: set[str] = set()
        for reg in self._registrations:
            if reg.name in seen:
                raise ValueError(
                    f"Duplicate stage registration for name: {reg.name!r}",
                )
            seen.add(reg.name)

    @property
    def togglable_names(self) -> frozenset[str]:
        """Names of stages the skip policy may disable."""
        return frozenset(reg.name for reg in self._registrations if reg.togglable)

    def build_for(self, enabled_stages: frozenset[str]) -> list[IPipelineStage]:
        # Return every stage in declaration order. Stages themselves
        # consult the skip policy + config; skipped stages record a
        # SKIPPED entry.
        return [reg.stage for reg in self._registrations]
