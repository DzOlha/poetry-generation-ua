"""GenerationStage — runs the LLM once to produce the initial poem."""
from __future__ import annotations

from src.domain.errors import LLMError
from src.domain.evaluation import StageRecord
from src.domain.models import Poem
from src.domain.pipeline_context import PipelineState
from src.domain.ports import ILLMProvider, ILogger, IPipelineStage
from src.infrastructure.tracing.stage_timer import StageTimer


class GenerationStage(IPipelineStage):
    """Calls ILLMProvider.generate() and records the initial poem."""

    STAGE_NAME = "initial_generation"

    def __init__(self, llm: ILLMProvider, logger: ILogger) -> None:
        self._llm = llm
        self._logger: ILogger = logger

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        if state.aborted:
            return

        with StageTimer() as t:
            try:
                raw = self._llm.generate(state.prompt)
                state.poem = Poem.from_text(raw).as_text() or raw
            except LLMError as exc:
                self._logger.error("LLM generation failed", error=str(exc))
                state.abort(f"generation failed: {exc}")
                state.tracer.add_stage(StageRecord(
                    name=self.STAGE_NAME,
                    input_summary=f"prompt ({len(state.prompt)} chars)",
                    error=str(exc),
                ))
                return

        parsed = Poem.from_text(state.poem)
        state.tracer.add_stage(StageRecord(
            name=self.STAGE_NAME,
            input_summary=f"prompt ({len(state.prompt)} chars)",
            output_summary=f"{parsed.line_count} lines generated",
            output_data=state.poem,
            metrics={"num_lines": parsed.line_count},
            duration_sec=t.elapsed,
        ))
