"""Application configuration loaded from environment variables.

Single source of truth for all runtime knobs. Services receive a frozen
AppConfig instance; they never read os.environ directly.

Usage:
    config = AppConfig.from_env()
    service = composition_root.build_poetry_service(config)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from src.domain.errors import ConfigurationError

_BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ValidationConfig:
    """All magic numbers used by validators and pipeline defaults.

    Centralising these makes them experiment-friendly: change one value in
    AppConfig.validation and every validator picks it up automatically.
    """

    rhyme_threshold: float = 0.55
    meter_allowed_mismatches: int = 2
    bsp_score_threshold: float = 0.6
    bsp_alternation_weight: float = 0.50
    bsp_variation_weight: float = 0.20
    bsp_stability_weight: float = 0.15
    bsp_balance_weight: float = 0.15

    def __post_init__(self) -> None:
        if not 0.0 <= self.rhyme_threshold <= 1.0:
            raise ConfigurationError(
                f"rhyme_threshold must be in [0, 1], got {self.rhyme_threshold}"
            )
        if self.meter_allowed_mismatches < 0:
            raise ConfigurationError(
                f"meter_allowed_mismatches must be >= 0, got {self.meter_allowed_mismatches}"
            )
        if not 0.0 <= self.bsp_score_threshold <= 1.0:
            raise ConfigurationError(
                f"bsp_score_threshold must be in [0, 1], got {self.bsp_score_threshold}"
            )


@dataclass(frozen=True)
class DetectionConfig:
    """Thresholds for brute-force meter/rhyme auto-detection.

    Higher thresholds yield fewer but more reliable classifications.
    ``sample_lines`` controls how many leading lines are sampled from each
    poem; set to 14 for sonnet compound-scheme detection.
    """

    meter_min_accuracy: float = 0.85
    rhyme_min_accuracy: float = 0.75
    sample_lines: int = 4
    feet_min: int = 2
    feet_max: int = 6

    def __post_init__(self) -> None:
        if not 0.0 <= self.meter_min_accuracy <= 1.0:
            raise ConfigurationError(
                f"meter_min_accuracy must be in [0, 1], got {self.meter_min_accuracy}"
            )
        if not 0.0 <= self.rhyme_min_accuracy <= 1.0:
            raise ConfigurationError(
                f"rhyme_min_accuracy must be in [0, 1], got {self.rhyme_min_accuracy}"
            )
        if self.sample_lines < 2:
            raise ConfigurationError(
                f"sample_lines must be >= 2, got {self.sample_lines}"
            )
        if not 1 <= self.feet_min <= self.feet_max:
            raise ConfigurationError(
                f"feet_min..feet_max must be 1 <= min <= max, got {self.feet_min}..{self.feet_max}"
            )


@dataclass(frozen=True)
class LLMReliabilityConfig:
    """Knobs for the LLM decorator stack (timeout + retry)."""

    timeout_sec: float = 60.0
    retry_max_attempts: int = 3
    retry_base_delay_sec: float = 1.0
    retry_max_delay_sec: float = 10.0
    retry_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.timeout_sec <= 0:
            raise ConfigurationError(
                f"timeout_sec must be > 0, got {self.timeout_sec}"
            )
        if self.retry_max_attempts < 1:
            raise ConfigurationError(
                f"retry_max_attempts must be >= 1, got {self.retry_max_attempts}"
            )


@dataclass(frozen=True)
class AppConfig:
    """Top-level runtime configuration."""

    # LLM
    llm_provider: str = ""  # "" = auto (gemini if API key set, else mock)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_temperature: float = 0.9
    gemini_max_tokens: int = 4096
    llm_reliability: LLMReliabilityConfig = field(default_factory=LLMReliabilityConfig)

    # Data paths
    corpus_path: Path = field(default_factory=lambda: _BASE_DIR / "corpus" / "uk_theme_reference_corpus.json")
    metric_examples_path: Path = field(
        default_factory=lambda: _BASE_DIR / "corpus" / "uk_metric-rhyme_reference_corpus.json",
    )

    # Embedding model
    labse_model_name: str = "sentence-transformers/LaBSE"
    offline_embedder: bool = False  # when True, use OfflineDeterministicEmbedder

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Validation knobs (nested, immutable)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Detection knobs (nested, immutable)
    detection: DetectionConfig = field(default_factory=DetectionConfig)

    KNOWN_LLM_PROVIDERS: frozenset[str] = frozenset({"", "gemini", "mock"})

    def __post_init__(self) -> None:
        if self.llm_provider and self.llm_provider not in self.KNOWN_LLM_PROVIDERS:
            raise ConfigurationError(
                f"Unknown llm_provider {self.llm_provider!r}, "
                f"expected one of {sorted(self.KNOWN_LLM_PROVIDERS - {''})}"
            )
        if not 0.0 <= self.gemini_temperature <= 2.0:
            raise ConfigurationError(
                f"gemini_temperature must be in [0, 2], got {self.gemini_temperature}"
            )
        if self.gemini_max_tokens <= 0:
            raise ConfigurationError(
                f"gemini_max_tokens must be > 0, got {self.gemini_max_tokens}"
            )
        if not 1 <= self.port <= 65535:
            raise ConfigurationError(f"port out of range: {self.port}")

    @classmethod
    def from_env(cls) -> AppConfig:
        """Build config from environment variables."""
        def _bool(name: str, default: bool = False) -> bool:
            return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "y", "on")

        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.9")),
            gemini_max_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "4096")),
            corpus_path=Path(
                os.getenv("CORPUS_PATH", str(_BASE_DIR / "corpus" / "uk_theme_reference_corpus.json"))
            ),
            metric_examples_path=Path(
                os.getenv(
                    "METRIC_EXAMPLES_PATH",
                    str(_BASE_DIR / "corpus" / "uk_metric-rhyme_reference_corpus.json"),
                )
            ),
            labse_model_name=os.getenv("LABSE_MODEL", "sentence-transformers/LaBSE"),
            offline_embedder=_bool("OFFLINE_EMBEDDER", False),
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8000")),
            debug=_bool("DEBUG", False),
        )
