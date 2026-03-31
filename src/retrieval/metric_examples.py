from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DATASET_PATH = "corpus/ukrainian_poetry_dataset.json"

# Mapping of English meter aliases to Ukrainian canonical names used in the dataset
_METER_ALIASES: dict[str, str] = {
    "iamb": "ямб",
    "trochee": "хорей",
    "dactyl": "дактиль",
    "amphibrach": "амфібрахій",
    "anapest": "анапест",
}


@dataclass(frozen=True)
class MetricExample:
    id: str
    meter: str
    feet: int
    scheme: str
    text: str
    verified: bool
    author: str | None = None
    note: str | None = None


def load_metric_dataset(path: Path) -> list[MetricExample]:
    """Load annotated poetry dataset from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    examples: list[MetricExample] = []
    for item in raw:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        examples.append(
            MetricExample(
                id=str(item.get("id", "")),
                meter=str(item.get("meter", "")),
                feet=int(item.get("feet", 0)),
                scheme=str(item.get("scheme", "")),
                text=text,
                verified=bool(item.get("verified", False)),
                author=item.get("author"),
                note=item.get("note"),
            )
        )
    return examples


def find_metric_examples(
    meter: str,
    feet: int,
    scheme: str,
    dataset_path: str | Path = _DEFAULT_DATASET_PATH,
    top_k: int = 3,
    verified_only: bool = False,
) -> list[MetricExample]:
    """Return up to *top_k* examples from the dataset matching the given meter, feet, and
    rhyme scheme.

    Verified examples are returned first.  Falls back to unverified examples when there
    are fewer than *top_k* verified ones (unless *verified_only* is True).

    Returns an empty list when the dataset file does not exist or no match is found.
    """
    path = Path(dataset_path)
    if not path.exists():
        return []

    dataset = load_metric_dataset(path)

    # Normalise: map English aliases to Ukrainian names used in the dataset
    meter_key = meter.strip().lower()
    meter_ua = _METER_ALIASES.get(meter_key, meter_key)

    scheme_upper = scheme.strip().upper()

    matched = [
        e for e in dataset
        if e.meter.lower() == meter_ua
        and e.feet == feet
        and e.scheme.upper() == scheme_upper
    ]

    if verified_only:
        matched = [e for e in matched if e.verified]
    else:
        # Verified first, then unverified
        matched = sorted(matched, key=lambda e: (not e.verified,))

    return matched[:top_k]
