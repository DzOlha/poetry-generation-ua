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
            raise UnsupportedConfigError(
                f"Unsupported meter: '{meter_name}'. Supported: {sorted(METER_TEMPLATES)}"
            )
        return list(METER_TEMPLATES[key])

    def supported_meters(self) -> tuple[str, ...]:
        return tuple(sorted(METER_TEMPLATES))
