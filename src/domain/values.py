"""Domain value enums — meter names, rhyme patterns, scenario categories.

These replace the string-typed fields that used to live on MeterSpec/RhymeScheme,
so unknown values are rejected at the boundary (API, CLI, config) rather than
at the bottom of the validator stack.
"""
from __future__ import annotations

from enum import Enum


class MeterName(str, Enum):
    """Canonical Ukrainian meter identifiers.

    Subclasses `str` so the enum values serialise directly in JSON, appear
    readable in logs, and interoperate with existing string-based corpora.
    """

    IAMB = "ямб"
    TROCHEE = "хорей"
    DACTYL = "дактиль"
    AMPHIBRACH = "амфібрахій"
    ANAPEST = "анапест"

    # English aliases kept as separate members so they round-trip through
    # repositories and configs that still use them.
    IAMB_EN = "iamb"
    TROCHEE_EN = "trochee"
    DACTYL_EN = "dactyl"
    AMPHIBRACH_EN = "amphibrach"
    ANAPEST_EN = "anapest"

    @classmethod
    def parse(cls, raw: str) -> MeterName:
        """Resolve a user-provided string to a MeterName, accepting aliases.

        Raises UnsupportedConfigError for any value outside the enum.
        """
        from src.domain.errors import UnsupportedConfigError

        key = (raw or "").strip().lower()
        for member in cls:
            if member.value == key:
                return member
        # Only advertise the canonical Ukrainian names in the user-facing
        # message — English aliases (iamb/trochee/…) are kept internally
        # for corpus round-tripping but surface as noise to end users.
        ukrainian = [
            MeterName.IAMB.value, MeterName.TROCHEE.value, MeterName.DACTYL.value,
            MeterName.AMPHIBRACH.value, MeterName.ANAPEST.value,
        ]
        raise UnsupportedConfigError(
            f"Невідомий метр: {raw!r}. "
            f"Підтримувані метри: {', '.join(ukrainian)}."
        )

    def canonical(self) -> MeterName:
        """Return the canonical Ukrainian spelling (collapses English aliases)."""
        mapping: dict[MeterName, MeterName] = {
            MeterName.IAMB_EN: MeterName.IAMB,
            MeterName.TROCHEE_EN: MeterName.TROCHEE,
            MeterName.DACTYL_EN: MeterName.DACTYL,
            MeterName.AMPHIBRACH_EN: MeterName.AMPHIBRACH,
            MeterName.ANAPEST_EN: MeterName.ANAPEST,
        }
        return mapping.get(self, self)


class RhymePattern(str, Enum):
    """Canonical rhyme-scheme patterns supported by the system."""

    ABAB = "ABAB"
    AABB = "AABB"
    ABBA = "ABBA"
    AAAA = "AAAA"

    @classmethod
    def parse(cls, raw: str) -> RhymePattern:
        """Resolve a user-provided string to a RhymePattern.

        Raises UnsupportedConfigError for any pattern outside the canonical set.
        """
        from src.domain.errors import UnsupportedConfigError

        key = (raw or "").strip().upper()
        for member in cls:
            if member.value == key:
                return member
        raise UnsupportedConfigError(
            f"Невідома схема римування: {raw!r}. "
            f"Підтримувані схеми: {', '.join(m.value for m in cls)}."
        )


class ScenarioCategory(str, Enum):
    """Evaluation-scenario category (normal/edge/corner)."""

    NORMAL = "normal"
    EDGE = "edge"
    CORNER = "corner"
