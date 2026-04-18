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
            "OUTPUT ENVELOPE (mandatory):\n"
            "Wrap your FINAL corrected poem between the literal tags <POEM> and </POEM>. "
            "You may reason freely BEFORE <POEM>. Everything between the tags "
            "must be ONLY clean Ukrainian poem lines in normal orthography, "
            "one line per verse line, no line numbers, no commentary. Emit "
            "</POEM> immediately after the last poem line and write nothing "
            "after it.\n\n"
            "STRICT FORMAT RULES FOR THE CONTENT BETWEEN <POEM>...</POEM>:\n"
            "The first token after <POEM> must be a Cyrillic letter — no "
            "punctuation, parenthesis, digit, or Latin letter may precede it. "
            "Every line between the tags must contain Ukrainian words; lines "
            "that are only punctuation, digits, or scansion are forbidden.\n\n"
            "IMPORTANT: the violations below may reference stress positions and "
            "syllable counts to explain WHAT is wrong. Do NOT copy that notation "
            "into your output. Your output must be plain Ukrainian poem lines in "
            "normal orthography — NO ALL-CAPS words, NO hyphenated syllables "
            "('За-гу-бив-ся'), NO parenthesized syllable numbers ('сло(1) во(2)'), "
            "NO scansion marks ('u u -', '(U)'), NO bare digit sequences, "
            "NO English commentary.\n\n"
            "POEM (with line numbers for reference):\n"
            f"{numbered}\n\n"
            "VIOLATIONS TO FIX:\n"
            f"{feedback_text}\n"
        )
