"""Ukrainian meter template provider."""
from __future__ import annotations

from src.domain.errors import UnsupportedConfigError
from src.domain.ports import IMeterTemplateProvider

# Ukrainian meter templates: one foot per entry.
METER_TEMPLATES: dict[str, list[str]] = {
    "ямб": ["u", "—"],
    "iamb": ["u", "—"],
    "хорей": ["—", "u"],
    "trochee": ["—", "u"],
    "дактиль": ["—", "u", "u"],
    "dactyl": ["—", "u", "u"],
    "амфібрахій": ["u", "—", "u"],
    "amphibrach": ["u", "—", "u"],
    "анапест": ["u", "u", "—"],
    "anapest": ["u", "u", "—"],
}


class UkrainianMeterTemplateProvider(IMeterTemplateProvider):
    """IMeterTemplateProvider for the five canonical Ukrainian meters."""

    def template_for(self, meter_name: str) -> list[str]:
        key = (meter_name or "").strip().lower()
        if key not in METER_TEMPLATES:
            # Advertise only the Ukrainian names to end users; English
            # aliases in ``METER_TEMPLATES`` exist for corpus/config
            # round-tripping but add noise to error messages.
            ukrainian = ["ямб", "хорей", "дактиль", "амфібрахій", "анапест"]
            raise UnsupportedConfigError(
                f"Невідомий метр: {meter_name!r}. "
                f"Підтримувані метри: {', '.join(ukrainian)}."
            )
        return list(METER_TEMPLATES[key])

    def supported_meters(self) -> tuple[str, ...]:
        return tuple(sorted(METER_TEMPLATES))
