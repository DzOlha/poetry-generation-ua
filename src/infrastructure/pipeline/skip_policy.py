"""Default IStageSkipPolicy implementation.

Skip rules:
  1. Skip everything after the pipeline aborts.
  2. For togglable stages, skip when the ablation config does not enable them.
  3. Mandatory stages (prompt construction, LLM generation, final metrics)
     always run — they are not in the togglable set.

The togglable set is injected so callers can add new ablation axes without
editing this class.
"""
from __future__ import annotations

from src.domain.evaluation import (
    STAGE_FEEDBACK_LOOP,
    STAGE_METRIC_EXAMPLES,
    STAGE_RETRIEVAL,
    STAGE_VALIDATION,
)
from src.domain.pipeline_context import PipelineState
from src.domain.ports import IStageSkipPolicy

_DEFAULT_TOGGLABLE_STAGES: frozenset[str] = frozenset({
    STAGE_RETRIEVAL,
    STAGE_METRIC_EXAMPLES,
    STAGE_VALIDATION,
    STAGE_FEEDBACK_LOOP,
})


class DefaultStageSkipPolicy(IStageSkipPolicy):
    """Skip policy: respect prior aborts and ablation-config toggles."""

    def __init__(
        self,
        togglable_stages: frozenset[str] = _DEFAULT_TOGGLABLE_STAGES,
    ) -> None:
        self._togglable = togglable_stages

    def should_skip(self, state: PipelineState, stage_name: str) -> bool:
        if state.aborted:
            return True
        if stage_name not in self._togglable:
            return False
        return not state.config.is_enabled(stage_name)
