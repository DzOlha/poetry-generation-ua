"""Allowlist-based poem output sanitizer.

A line of real Ukrainian verse contains **only**:

* Ukrainian Cyrillic letters
* the combining acute accent (``\u0301``) used for stress marking
* a single apostrophe (``'`` / ``’`` / ``ʼ``)
* basic punctuation: ``. , ! ? : ; …``
* dashes: ``— – -``
* quotes: ``" „ " " « »``
* parentheses for poetic asides
* whitespace

Anything else — Latin letters, ASCII digits, pipes, arrows, slashes,
backslashes, brackets, mathematical symbols, emoji — marks the line as
non-Ukrainian-verse and the sanitizer drops it. This allowlist approach
replaces an earlier blacklist of regex patterns that was continuously
broken by new leak shapes (pure-English drafts, slashes as separators,
parenthesised syllable counts, etc.): if a character is not in the
allowed set, we do not need to enumerate *why* the line is garbage.

The classifier still runs two complementary filters on top of the
allowlist — they catch Cyrillic-only garbage that would otherwise slip
through because its characters happen to be legal in isolation:

* **ALL-CAPS stress marker.** A lowercase Cyrillic letter immediately
  followed by an uppercase Cyrillic letter inside a word (``КрО``,
  ``рЕж``) is how the model marks stress in leaked drafts.
* **Syllable hyphenation.** Two or more intra-word hyphens between
  Cyrillic letters (``за-гу-бив-ся``, ``о-бе-рЕж-ні``) mark a manual
  syllable split.
* **Bullet prefix.** ``* ``, ``# ``, ``// `` and plain ASCII ``- `` at
  the start of a line are comment/list markers. The em-dash ``— `` is
  deliberately allowed because it opens dialogue in Ukrainian verse.

Before classification the sanitizer also runs a **salvage pass** that
strips parenthesised scansion blocks (``(Те-мря-ва)``, ``(4+5=9)``,
``(wait, let me check)``) from otherwise-clean lines. Legitimate
parenthetical asides (``(мовчки, тихо)``) survive because their
content itself passes the allowlist.

If every line is filtered the sanitizer returns ``""`` — the
``SanitizingLLMProvider`` decorator turns that into an ``LLMError`` so
the retry layer asks the model for another attempt instead of letting
a garbage response reach the validator.
"""
from __future__ import annotations

import re

from src.domain.ports import IPoemOutputSanitizer

# --- Allowlist -------------------------------------------------------------
#
# Character class enumerating every codepoint a legitimate Ukrainian poem
# line may contain. Everything outside this set flags the line as garbage.
# Whitespace covers space and tab only — newlines are handled at the
# line-splitting level above.
_ALLOWED_LINE_RE = re.compile(
    r"^["
    r"А-Яа-я"           # Cyrillic letters (covers most of the Ukrainian alphabet)
    r"ІЇЄҐіїєґ"         # Ukrainian-specific letters
    r"\u0301"           # combining acute accent (stress marker)
    r"'\u2018\u2019\u02BC"  # apostrophe variants: '  ‘  ’  ʼ
    r" \t"              # whitespace
    r".,!?:;"           # basic punctuation
    r"\u2026"           # ellipsis …
    r"\u2014\u2013\-"   # em-dash, en-dash, hyphen-minus
    r'"'                # straight double quote
    r"\u201C\u201D"     # curly double quotes “ ”
    r"\u201E\u201A\u201B"  # low-9 / high-reversed quotes „ ‚ ‛
    r"\u00AB\u00BB"     # guillemets « »
    r"()"               # parentheses for poetic asides
    r"]+$",
)

# --- Behavioural rules (Cyrillic-only garbage the allowlist cannot spot) ---
_CYRILLIC_LOWER_UPPER_RE = re.compile(r"[а-яіїєґ'ʼ][А-ЯІЇЄҐ]")
_INTRAWORD_HYPHEN_RE = re.compile(r"[А-Яа-яІЇЄҐіїєґ'ʼ]-[А-Яа-яІЇЄҐіїєґ'ʼ]")
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:\*|#|//|-\s)")
_CYRILLIC_LETTER_RE = re.compile(r"[А-Яа-яІЇЄҐіїєґ]")

# --- Salvage pass: detect scansion flavour of a parenthesised chunk --------
_PAREN_BLOCK_RE = re.compile(r"\s*\([^()]*\)")
_DIGIT_RE = re.compile(r"\d")
_LATIN_RE = re.compile(r"[A-Za-z]")
_SCANSION_PAREN_INNER_RE = re.compile(r"\u2192|->|=>")
# Models often write ``word. (scansion).`` in CoT; stripping the paren
# leaves ``word..`` (double period). Collapse runs of duplicated
# sentence punctuation to a single mark. ``!`` and ``?`` are excluded —
# ``!!``, ``?!``, ``!?`` are legitimate in Ukrainian verse for emphasis.
_PUNCT_RUN_RE = re.compile(r"([.,;:])\1+")


class RegexPoemOutputSanitizer(IPoemOutputSanitizer):
    """Drops lines whose characters are not drawn from the Ukrainian verse alphabet."""

    def sanitize(self, text: str) -> str:
        if not text:
            return text
        kept: list[str] = []
        for line in text.splitlines():
            if not line.strip():
                kept.append(line)
                continue
            salvaged = self._salvage(line)
            if not salvaged.strip():
                continue
            if self._is_garbage(salvaged):
                continue
            kept.append(salvaged)
        cleaned = "\n".join(kept).strip()
        if not cleaned:
            return ""
        return cleaned + "\n"

    @classmethod
    def _salvage(cls, line: str) -> str:
        """Strip parenthesised scansion chunks from an otherwise clean line.

        Repeated because leaked CoT sometimes stacks several parenthetical
        blocks on the same line. After paren-stripping, duplicate
        sentence-end punctuation (``..``, ``,,``, ``;;``) is collapsed to a
        single mark — the common artefact from a pattern like
        ``"word. (scansion)."`` where the outer period was scansion's own
        closure, not the poem's.
        """
        previous = None
        current = line
        while previous != current:
            previous = current
            current = _PAREN_BLOCK_RE.sub(
                lambda m: "" if cls._paren_is_scansion(m.group(0)) else m.group(0),
                current,
            )
        current = _PUNCT_RUN_RE.sub(r"\1", current)
        return current.rstrip()

    @staticmethod
    def _paren_is_scansion(chunk: str) -> bool:
        inner = chunk.strip().lstrip("(").rstrip(")")
        if not inner:
            return False
        if _DIGIT_RE.search(inner):
            return True
        if _LATIN_RE.search(inner):
            return True
        if _SCANSION_PAREN_INNER_RE.search(inner):
            return True
        if _CYRILLIC_LOWER_UPPER_RE.search(inner):
            return True
        return bool(_INTRAWORD_HYPHEN_RE.search(inner))

    @staticmethod
    def _is_garbage(line: str) -> bool:
        if not _ALLOWED_LINE_RE.match(line):
            # Contains at least one character that a Ukrainian poem line
            # has no business containing (Latin letter, ASCII digit, ``|``,
            # ``/``, ``\``, ``[``, ``<``, math/emoji, etc.).
            return True
        if not _CYRILLIC_LETTER_RE.search(line):
            # Every char is in the allowlist but none of them is a
            # Cyrillic letter — i.e. the line is pure punctuation (``).``,
            # ``,.``, ``—``) leaked from a truncated CoT fragment.
            return True
        if _CYRILLIC_LOWER_UPPER_RE.search(line):
            return True
        if len(_INTRAWORD_HYPHEN_RE.findall(line)) >= 2:
            return True
        return bool(_BULLET_PREFIX_RE.search(line))
