"""Poem aggregate — the single point that splits raw text into usable lines."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Lines that are clearly LLM chain-of-thought leaking into the poem body:
# scansion markup like "(u u - u u", "(U)", "( - )", arrows "->",
# English commentary ("Wait", "Let", "Perfect"), markdown bullets, or
# any Latin letters (the poem is Ukrainian, so Latin text is reasoning).
_LATIN_RE = re.compile(r"[A-Za-z]")
_SCANSION_RE = re.compile(r"\([\s\-uU\d]*\)|->|\bWait\b|\bLet\b|\bPerfect\b")
# Syllable numbering like "сло(1) во(2)" or "А (1) ни (2) ні (3)".
_PAREN_DIGIT_RE = re.compile(r"\(\s*\d+\s*\)")
# Pure scansion lines: only digits, whitespace, hyphens, or dashes.
_DIGIT_ONLY_RE = re.compile(r"^[\d\s\-–—]+$")
# ALL-CAPS Cyrillic tokens (≥2 letters), e.g. "ДУТЬ", "СЛАВ", "РІД".
# Two or more of these in one line = scansion markup, not poetry.
_CAPS_CYR_TOKEN_RE = re.compile(r"[А-ЯІЇЄҐ]{2,}")
# Any Cyrillic letter — a real poem line must contain at least one.
# Fragments like ")." or "— — —" slip past every other filter but aren't poetry.
_CYR_LETTER_RE = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
# Leading "N:" or "N." echoed back from the numbered-regen prompt template
# (e.g. "1: рядок", "2. рядок"). We strip these; the remainder is re-evaluated.
_LINE_NUMBER_PREFIX_RE = re.compile(r"^\d+\s*[:.]\s*")
# Minimum Cyrillic letters for a plausible poem line — catches scansion
# fragments like "1: КО" (→ "КО" after strip), "жен", "шу" that otherwise
# slip through the filter because they are short real Cyrillic tokens.
_MIN_CYR_LETTERS = 5


def _strip_line_number_prefix(line: str) -> str:
    """Strip a single "N:" / "N." prefix if present — echo of the regen prompt."""
    return _LINE_NUMBER_PREFIX_RE.sub("", line, count=1).strip()


def _is_poem_line(line: str) -> bool:
    if not line:
        return False
    if line[0] in "*#>`":
        return False
    if not _CYR_LETTER_RE.search(line):
        return False
    if _LATIN_RE.search(line):
        return False
    if _SCANSION_RE.search(line):
        return False
    if _PAREN_DIGIT_RE.search(line):
        return False
    if _DIGIT_ONLY_RE.match(line):
        return False
    if len(_CYR_LETTER_RE.findall(line)) < _MIN_CYR_LETTERS:
        return False
    return len(_CAPS_CYR_TOKEN_RE.findall(line)) < 2


@dataclass(frozen=True)
class Poem:
    """A parsed poem, exposing line-level behaviour its consumers used to inline.

    Validators, merger, reporter, and stages all used to import
    `split_nonempty_lines` directly. Routing that through a `Poem` aggregate
    means (a) line-splitting logic is centralised, (b) consumers depend only
    on domain objects, and (c) future language-specific parsing can plug in
    via `Poem.from_text` without touching downstream code.
    """

    lines: tuple[str, ...]

    @classmethod
    def from_text(cls, text: str) -> Poem:
        """Parse raw poem text into a Poem, dropping blank lines, whitespace, and CoT leakage."""
        raw_lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        stripped = [_strip_line_number_prefix(ln) for ln in raw_lines]
        lines = tuple(ln for ln in stripped if _is_poem_line(ln))
        return cls(lines=lines)

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines

    def as_text(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.lines else "")
