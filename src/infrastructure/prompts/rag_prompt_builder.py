"""RAG prompt builder — constructs the LLM prompt from request + retrieved context."""
from __future__ import annotations

from src.domain.models import GenerationRequest, MetricExample, RetrievedExcerpt
from src.domain.ports import IPromptBuilder


class RagPromptBuilder(IPromptBuilder):
    """Builds a RAG (retrieval-augmented generation) prompt."""

    def build(
        self,
        request: GenerationRequest,
        retrieved: list[RetrievedExcerpt],
        examples: list[MetricExample],
    ) -> str:
        excerpts_section = self._format_excerpts(retrieved)
        metric_section = self._format_metric_section(request, examples)
        structure_desc = self._format_structure(request)

        return (
            "Use the following poetic excerpts as thematic inspiration (do not copy):\n"
            f"{excerpts_section}\n"
            f"{metric_section}\n"
            f"Theme: {request.theme}\n"
            f"Meter: {request.meter.name}\n"
            f"Rhyme scheme: {request.rhyme.pattern}\n"
            f"Structure: {structure_desc}\n"
            f"Generate a Ukrainian poem with exactly {request.structure.total_lines} lines."
        )

    @staticmethod
    def _format_excerpts(retrieved: list[RetrievedExcerpt]) -> str:
        return "\n".join(r.excerpt.text.strip() for r in retrieved)

    @staticmethod
    def _format_metric_section(request: GenerationRequest, examples: list[MetricExample]) -> str:
        if not examples:
            return ""
        examples_text = "\n\n".join(e.text.strip() for e in examples)
        return (
            f"\nUse these verified examples as METER and RHYME reference "
            f"(they demonstrate {request.meter.name} meter with {request.rhyme.pattern} rhyme scheme"
            f" — follow this rhythm and rhyme pattern exactly):\n"
            f"{examples_text}\n"
        )

    @staticmethod
    def _format_structure(request: GenerationRequest) -> str:
        s = request.structure
        plural = "s" if s.stanza_count > 1 else ""
        return (
            f"{s.stanza_count} stanza{plural} of {s.lines_per_stanza} lines each "
            f"({s.total_lines} lines total)"
        )
