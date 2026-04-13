"""RetrievalStage — loads the corpus and retrieves theme-similar excerpts."""
from __future__ import annotations

from src.domain.errors import DomainError
from src.domain.evaluation import StageRecord
from src.domain.pipeline_context import PipelineState
from src.domain.ports import ILogger, IPipelineStage, IRetriever, IStageSkipPolicy, IThemeRepository
from src.infrastructure.tracing.stage_timer import StageTimer


class RetrievalStage(IPipelineStage):
    """Fetches the top-k thematically similar corpus excerpts."""

    STAGE_NAME = "retrieval"

    def __init__(
        self,
        theme_repo: IThemeRepository,
        retriever: IRetriever,
        skip_policy: IStageSkipPolicy,
        logger: ILogger,
    ) -> None:
        self._theme_repo = theme_repo
        self._retriever = retriever
        self._skip = skip_policy
        self._logger: ILogger = logger

    @property
    def name(self) -> str:
        return self.STAGE_NAME

    def run(self, state: PipelineState) -> None:
        if state.aborted:
            return

        if self._skip.should_skip(state, self.STAGE_NAME):
            state.tracer.add_stage(StageRecord(
                name=self.STAGE_NAME,
                input_summary="SKIPPED (config.retrieval disabled)",
                output_summary="—",
                metrics={"num_retrieved": 0},
            ))
            return

        theme = state.theme
        corpus_size = 0
        with StageTimer() as t:
            try:
                corpus = self._theme_repo.load()
                corpus_size = len(corpus)
                state.retrieved = self._retriever.retrieve(
                    theme, corpus, top_k=state.top_k,
                )
            except DomainError as exc:
                self._logger.warning("retrieval stage failed", error=str(exc))
                state.tracer.add_stage(StageRecord(
                    name=self.STAGE_NAME,
                    input_summary=f"theme={theme!r}",
                    error=str(exc),
                ))
                state.retrieved = []
                return

        retrieved = state.retrieved
        retrieved_data = [
            {"similarity": round(r.similarity, 4), "text": r.excerpt.text}
            for r in retrieved
        ]
        top_sim = retrieved[0].similarity if retrieved else 0.0
        output_summary = (
            f"retrieved {len(retrieved)} poems, top_sim={top_sim:.4f}"
            if retrieved else "no results"
        )
        state.tracer.add_stage(StageRecord(
            name=self.STAGE_NAME,
            input_summary=f"theme={theme!r}, corpus_size={corpus_size}",
            input_data={"theme": theme, "corpus_size": corpus_size},
            output_summary=output_summary,
            output_data=retrieved_data,
            metrics={
                "num_retrieved": len(retrieved),
                "top_similarity": top_sim,
            },
            duration_sec=t.elapsed,
        ))
