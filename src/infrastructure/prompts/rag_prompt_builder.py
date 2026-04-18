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
            f"Generate a Ukrainian poem with exactly {request.structure.total_lines} lines.\n"
            "\n"
            "OUTPUT ENVELOPE (mandatory):\n"
            "Wrap your FINAL poem between the literal tags <POEM> and </POEM>.\n"
            "You may reason freely BEFORE <POEM>. Everything between <POEM> "
            "and </POEM> must be ONLY clean Ukrainian poem lines in normal "
            "orthography — one line per verse line, exactly "
            f"{request.structure.total_lines} lines, no blank separators other "
            "than one newline between lines. Emit </POEM> immediately after "
            "the last poem line; write nothing after it.\n"
            "\n"
            "STRICT FORMAT RULES FOR THE CONTENT BETWEEN <POEM>...</POEM> — "
            "violating any is a failure:\n"
            "- The first token after <POEM> MUST be a Cyrillic letter. "
            "No punctuation, parenthesis, digit, or Latin letter may precede it.\n"
            "- Every output line MUST contain Ukrainian words; lines that are only "
            "punctuation, digits, or scansion are forbidden.\n"
            "- NO ALL-CAPS words marking stress (forbidden: 'І-ДУТЬ', 'СЛАВ-ний', 'БІЙ').\n"
            "- NO syllable hyphenation inside words (forbidden: 'За-гу-бив-ся', 'ле-тить').\n"
            "- NO syllable numbering in parentheses "
            "(forbidden: 'Слу(1) жи(2) ли(3)', 'А (1) ни (2)').\n"
            "- NO scansion marks ('u u -', '( - )', '(U)', '->').\n"
            "- NO bare number sequences like '1 2 3 4 5 6 7 8'.\n"
            "- NO English words, commentary, analysis, drafts, alternatives, "
            "markdown, bullets, line numbers, or explanations between the tags."
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
