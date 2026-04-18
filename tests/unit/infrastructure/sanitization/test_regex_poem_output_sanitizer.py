"""Tests for `RegexPoemOutputSanitizer`."""
from __future__ import annotations

import pytest

from src.infrastructure.sanitization import RegexPoemOutputSanitizer


@pytest.fixture
def sanitizer() -> RegexPoemOutputSanitizer:
    return RegexPoemOutputSanitizer()


class TestCleanPoemPassesThrough:
    def test_clean_ukrainian_poem_unchanged(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        poem = (
            "Тихо спить у місті ніч\n"
            "Ліхтарі горять в імлі\n"
            "Тіні зрадника проти вічі\n"
            "Шепіт долі на землі\n"
        )
        assert sanitizer.sanitize(poem) == poem

    def test_em_dash_at_line_start_preserved(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        poem = "— Стривай, — шепнула ніч\nЇй луна відповіла\n"
        assert sanitizer.sanitize(poem).strip() == poem.strip()

    def test_empty_input_passes_through(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        assert sanitizer.sanitize("") == ""


class TestGarbageLinesDropped:
    def test_parenthesized_digit_line_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\n(1), тІ(4), мЕ(7). Perfect.\nЛіхтарі горять\n"
        out = sanitizer.sanitize(raw)
        assert "Perfect" not in out
        assert "(1)" not in out
        assert "Тихо спить" in out
        assert "Ліхтарі горять" in out

    def test_bullet_commentary_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\n* C2: — на 9 складів коротше\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert "* C2" not in out
        assert "Тихо спить" in out

    def test_english_reasoning_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = (
            "Тихо спить\n"
            'Rhyme with "безмежні": обережні, незалежні.\n'
            'Wait, "мої" -> мо-Ї.\n'
            "Ліхтарі\n"
        )
        out = sanitizer.sanitize(raw)
        assert "Rhyme with" not in out
        assert "Wait" not in out
        assert "Тихо спить" in out
        assert "Ліхтарі" in out

    def test_bare_digit_sequence_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\n1 2 3 | 4 5 6 | 7 8\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert "1 2 3" not in out
        assert "|" not in out

    def test_allcaps_stress_marker_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\nКрОки мої обережні\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert "КрОки" not in out
        assert "Тихо спить" in out

    def test_syllable_hyphenation_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = (
            "Тихо спить\n"
            "КрО-ки мо-Ї о-бе-рЕж-ні -> 1 2 3 4 5 6 7 8.\n"
            "Ліхтарі\n"
        )
        out = sanitizer.sanitize(raw)
        assert "о-бе-рЕж-ні" not in out
        assert "->" not in out

    def test_scansion_paren_marker_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо (U) спить\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert "(U)" not in out
        assert "Ліхтарі" in out


class TestSalvageParenScansion:
    def test_strips_scansion_paren_and_keeps_clean_prefix(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # Real Gemini leak: clean Cyrillic line followed by parenthesized
        # syllable breakdown. Prefix is legitimate poetry — keep it.
        raw = "Темрява хутає місто, (Те-мря-ва ху-та-є мі-сто)\n"
        assert sanitizer.sanitize(raw) == "Темрява хутає місто,\n"

    def test_strips_paren_with_digits(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Світять вогні, як намисто (4+5=9)\n"
        assert sanitizer.sanitize(raw) == "Світять вогні, як намисто\n"

    def test_strips_paren_with_english_reasoning(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Світять вогні, як намисто (wait, let me check)\n"
        assert sanitizer.sanitize(raw) == "Світять вогні, як намисто\n"

    def test_preserves_clean_parenthetical_aside(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # A legitimate poetic aside with plain Cyrillic content must NOT
        # be stripped — only scansion-flavoured parens go.
        raw = "Я думав (мовчки, тихо) про зорю\n"
        assert sanitizer.sanitize(raw) == raw

    def test_strips_multiple_stacked_scansion_parens(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Темрява хутає місто (Те-мря-ва) (ху-та-є) далі\n"
        assert sanitizer.sanitize(raw) == "Темрява хутає місто далі\n"

    def test_collapses_duplicate_trailing_periods(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # Observed artefact: model writes ``word. (scansion).`` in CoT,
        # salvage strips the paren but leaves both periods → ``word..``.
        raw = "В селян робота, в діток — клас. (0 1 0 1 0 1 0 1).\n"
        assert sanitizer.sanitize(raw) == "В селян робота, в діток — клас.\n"

    def test_keeps_intentional_doubled_exclamation(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # ``!!``, ``?!``, ``!?`` are legitimate emphasis in Ukrainian
        # verse — do NOT collapse them.
        raw = "Невже це правда?!\nКоли ж вона вже тут!!\n"
        assert sanitizer.sanitize(raw) == raw


class TestAllowlistStrictness:
    def test_pure_english_line_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = (
            "Тихо спить\n"
            "The sky looks down with stars, / But nobody needs anyone.\n"
            "Ліхтарі\n"
        )
        out = sanitizer.sanitize(raw)
        assert "The sky" not in out
        assert "/" not in out
        assert "Тихо спить" in out
        assert "Ліхтарі" in out

    def test_short_english_label_dropped(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\nOr:\nNo.\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert "Or:" not in out
        assert "No." not in out
        assert out == "Тихо спить\nЛіхтарі\n"

    def test_accented_vowels_allowed(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # Combining acute accent marks stress in modern Ukrainian typography
        # (``Сві́тять вогні́``) — must NOT be treated as a foreign character.
        raw = "Сві́тять вогні́, як нами́сто\n"
        assert sanitizer.sanitize(raw) == raw

    def test_ellipsis_and_curly_quotes_allowed(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "«Тиша…» — шепнула ніч\n"
        assert sanitizer.sanitize(raw) == raw

    def test_slash_not_in_allowlist_drops_line(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\nзима/весна/літо\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        # ``/`` is not part of the Ukrainian verse alphabet — even with
        # only Cyrillic surrounding it the line is rejected.
        assert "зима/весна" not in out
        assert out == "Тихо спить\nЛіхтарі\n"

    def test_emoji_drops_line(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "Тихо спить\nТіні зрадника 💔\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert "💔" not in out

    def test_pure_punctuation_drops_line(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # Real failure from a truncated CoT: the model emitted just ``).``
        # as the final "line" after its reasoning was cut off. All chars
        # are in the allowlist but none of them is a Cyrillic letter.
        raw = ").\nТихо спить\n,.\n"
        out = sanitizer.sanitize(raw)
        assert ")." not in out
        assert ",." not in out
        assert "Тихо спить" in out

    def test_lone_dash_drops_line(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # Em-dash alone is not a verse line — a real Ukrainian dialogue
        # line starts with ``— `` then Cyrillic words follow.
        raw = "Тихо спить\n—\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert out == "Тихо спить\nЛіхтарі\n"


class TestFallbackBehaviour:
    def test_all_lines_garbage_returns_empty(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        raw = "1 2 3 4\n* Perfect.\nWait, let me think.\n"
        # If nothing survives, return empty string — the decorator turns
        # that into an LLMError so retry can ask for another attempt.
        # Silently returning the original garbage poisons the validator.
        assert sanitizer.sanitize(raw) == ""

    def test_idempotent(self, sanitizer: RegexPoemOutputSanitizer) -> None:
        raw = "Тихо спить\n(1), tІ(4), мЕ(7). Perfect.\nЛіхтарі горять\n"
        once = sanitizer.sanitize(raw)
        twice = sanitizer.sanitize(once)
        assert once == twice

    def test_blank_lines_preserved_as_stanza_breaks(
        self, sanitizer: RegexPoemOutputSanitizer,
    ) -> None:
        # Blank lines mark stanza boundaries in Ukrainian verse, so the
        # sanitizer must not collapse them — only garbage lines go.
        raw = "Тихо спить\n\n* drop me\nЛіхтарі\n"
        out = sanitizer.sanitize(raw)
        assert out == "Тихо спить\n\nЛіхтарі\n"
