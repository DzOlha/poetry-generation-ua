"""IRegenerationPromptBuilder adapters — build the prompt used by LLM.regenerate_lines."""
from __future__ import annotations

from src.domain.ports import IRegenerationPromptBuilder


class NumberedLinesRegenerationPromptBuilder(IRegenerationPromptBuilder):
    """Builds a numbered-lines regeneration prompt.

    Produces the exact prompt shape that ``BaseLLMProvider._build_regeneration_prompt``
    used to inline: numbered poem, bullet-list of violations, instruction to
    return the complete poem with only the flagged lines rewritten.
    """

    def build(self, poem: str, feedback_messages: list[str]) -> str:
        feedback_text = "\n".join(f"- {f}" for f in feedback_messages)
        lines = poem.strip().splitlines()
        numbered = "\n".join(f"{i + 1}: {ln}" for i, ln in enumerate(lines))
        return (
            "You are given a Ukrainian poem with line numbers and a list of violations.\n"
            "Fix ONLY the lines mentioned in the feedback. Copy all other lines exactly unchanged.\n"
            "Return the COMPLETE poem — every line, in the correct order — "
            "with no line numbers, no commentary, no markdown.\n\n"
            "POEM (with line numbers for reference):\n"
            f"{numbered}\n\n"
            "VIOLATIONS TO FIX:\n"
            f"{feedback_text}\n"
        )
