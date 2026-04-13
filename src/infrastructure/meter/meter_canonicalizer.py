"""Meter-name canonicalisation adapter."""
from __future__ import annotations

from src.domain.ports import IMeterCanonicalizer

# Canonical mapping from English meter names to Ukrainian names.
_METER_ALIASES: dict[str, str] = {
    "iamb": "ямб",
    "trochee": "хорей",
    "dactyl": "дактиль",
    "amphibrach": "амфібрахій",
    "anapest": "анапест",
}


class UkrainianMeterCanonicalizer(IMeterCanonicalizer):
    """Maps English aliases to Ukrainian meter names and normalises casing."""

    def canonicalize(self, name: str) -> str:
        key = (name or "").strip().lower()
        return _METER_ALIASES.get(key, key)
