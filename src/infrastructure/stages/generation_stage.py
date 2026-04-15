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

        expected_lines = state.request.structure.total_lines
        with StageTimer() as t:
            try:
                raw = self._llm.generate(state.prompt)
                parsed = Poem.from_text(raw)
                # If the CoT filter had to strip so much that the remaining
                # body is materially shorter than asked for, the "poem" is
                # almost certainly scansion/reasoning fragments (e.g. lone
                # ").") — keep the raw output so validators fail loudly and
                # the feedback iterator regenerates from scratch instead of
                # treating a broken fragment as a legitimate first draft.
                if parsed.line_count < expected_lines:
                    state.poem = raw
                else:
                    state.poem = parsed.as_text()
            except LLMError as exc:
                self._logger.error("LLM generation failed", error=str(exc))
                state.abort(f"generation failed: {exc}")
                state.tracer.add_stage(StageRecord(
                    name=self.STAGE_NAME,
                    input_summary=f"prompt ({len(state.prompt)} chars)",
                    error=str(exc),
                ))
                return

        final_parsed = Poem.from_text(state.poem)
        state.tracer.add_stage(StageRecord(
            name=self.STAGE_NAME,
            input_summary=f"prompt ({len(state.prompt)} chars)",
            output_summary=f"{final_parsed.line_count} lines generated",
            output_data=state.poem,
            metrics={"num_lines": final_parsed.line_count},
            duration_sec=t.elapsed,
        ))
