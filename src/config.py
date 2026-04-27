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

# Per-million-token prices used by EstimatedCostCalculator when no
# GEMINI_INPUT_PRICE_PER_M / GEMINI_OUTPUT_PRICE_PER_M is supplied. The
# numbers match Gemini 3.1 Pro Preview at ≤200K context and are the single
# source of truth for both the dataclass default and the env-loader fallback.
_GEMINI_DEFAULT_INPUT_PRICE_PER_M = 2.0
_GEMINI_DEFAULT_OUTPUT_PRICE_PER_M = 12.0


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
    ``sample_lines`` is fixed at 4 (quatrain) — the only stanza size
    currently supported by the rhyme scheme extractor.
    """

    meter_min_accuracy: float = 0.85
    # Detection is intentionally looser than generation/validation. At a
    # four-line sample there are typically only two rhyme pairs, so the
    # aggregate accuracy can only be 0.0 / 0.5 / 1.0 — a 0.75 cutoff would
    # silently demand *both* pairs pass. That wrongly rejects quatrains
    # where one pair is a slant rhyme (e.g. "душу / мусиш"). 0.5 admits the
    # scheme as soon as a single solid pair supports it, while still
    # filtering the all-mismatch case.
    rhyme_min_accuracy: float = 0.5
    sample_lines: int = 4
    # Detection sweep covers the same foot range as generation/validation
    # (1–6), so a poem the system itself can produce is also a poem the
    # system can recognise. 1-foot meters (e.g. anapest «Мерехтить / Мов
    # перлина») are short and rare but legitimate. Longer lines fall out
    # naturally via `line_length_ok` — a 6-syllable line vs a 1-foot
    # expected pattern fails length tolerance long before scoring.
    feet_min: int = 1
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
        if self.sample_lines != 4:
            raise ConfigurationError(
                f"sample_lines must be 4 (quatrain), got {self.sample_lines}"
            )
        if not 1 <= self.feet_min <= self.feet_max:
            raise ConfigurationError(
                f"feet_min..feet_max must be 1 <= min <= max, got {self.feet_min}..{self.feet_max}"
            )


@dataclass(frozen=True)
class LLMReliabilityConfig:
    """Knobs for the LLM decorator stack (timeout + retry).

    Defaults are tuned for reasoning-first models (Gemini Pro 2.5 / 3.x)
    whose CoT commonly takes 60-120 s per call. 120 s accommodates the
    upper end of legitimate reasoning; more than that usually means the
    model has wandered and ``TimeoutLLMProvider`` should abort so the
    feedback iterator can move on. Retries are kept at 2 because
    re-submitting after a timeout rarely helps (the next attempt tends
    to hit the same ceiling) — but transient 5xx / rate-limit responses
    still get a second try.
    """

    timeout_sec: float = 120.0
    retry_max_attempts: int = 2
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
class LLMInfo:
    """Human-facing summary of the active LLM wiring.

    Handlers consume this to display "which provider/model will generate
    the poem" on forms and to block submission when the stack cannot do
    real generation (e.g. GEMINI_API_KEY missing).
    """

    provider: str          # "gemini" / "mock" / custom registered name
    model: str             # "gemini-3.1-pro-preview" for real providers; "—" for mock
    ready: bool            # True = capable of real generation
    error: str | None = None  # user-facing message when ready=False


@dataclass(frozen=True)
class AppConfig:
    """Top-level runtime configuration."""

    # LLM
    llm_provider: str = ""  # "" = auto (gemini if API key set, else mock)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-pro-preview"
    gemini_temperature: float = 0.9
    # 8192 gives reasoning models (2.5+ / 3.x) headroom for chain-of-thought
    # plus the final ``<POEM>...</POEM>`` block. At 4096 Gemini Pro typically
    # hits the ceiling mid-CoT and the envelope is never emitted.
    gemini_max_tokens: int = 8192
    # When True, pass ``ThinkingConfig(thinking_budget=0, include_thoughts=False)``
    # to tell Gemini to skip reasoning entirely. Defaults to False because
    # thinking-only variants (e.g. Gemini 3.x Pro preview) reject budget 0
    # with ``INVALID_ARGUMENT``. Enable only for models that support it.
    gemini_disable_thinking: bool = False
    # Per-million-token prices used by EstimatedCostCalculator to turn
    # token counts into an approximate USD bill in batch runs. Override
    # via GEMINI_INPUT_PRICE_PER_M / GEMINI_OUTPUT_PRICE_PER_M env vars
    # when you switch to a cheaper Flash-tier model. Module-level
    # constants keep the dataclass default and the env-loader fallback
    # in sync.
    gemini_input_price_per_m: float = _GEMINI_DEFAULT_INPUT_PRICE_PER_M
    gemini_output_price_per_m: float = _GEMINI_DEFAULT_OUTPUT_PRICE_PER_M
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
        if self.gemini_input_price_per_m < 0:
            raise ConfigurationError(
                f"gemini_input_price_per_m must be >= 0, got {self.gemini_input_price_per_m}"
            )
        if self.gemini_output_price_per_m < 0:
            raise ConfigurationError(
                f"gemini_output_price_per_m must be >= 0, got {self.gemini_output_price_per_m}"
            )
        if not 1 <= self.port <= 65535:
            raise ConfigurationError(f"port out of range: {self.port}")

    def llm_info(self) -> LLMInfo:
        """Resolve the active LLM provider + model and surface readiness.

        The factory auto-falls-back to a `MockLLMProvider` when no API key
        is set, which silently returns canned test poems. For the UI that's
        undesirable — users expect real generation, so we flag the auto-
        fallback case as `ready=False` with a plain-language error. Explicit
        `LLM_PROVIDER=mock` is treated as intentional (tests / local demos)
        and stays `ready=True`.
        """
        explicit = self.llm_provider
        if explicit == "mock":
            return LLMInfo(provider="mock", model="—", ready=True)
        if explicit == "gemini":
            if not self.gemini_api_key:
                return LLMInfo(
                    provider="gemini",
                    model=self.gemini_model,
                    ready=False,
                    error=(
                        "Не знайдено GEMINI_API_KEY. Додайте ключ у змінну "
                        "середовища GEMINI_API_KEY, щоб увімкнути генерацію."
                    ),
                )
            return LLMInfo(provider="gemini", model=self.gemini_model, ready=True)
        # Auto-resolve (empty llm_provider)
        if self.gemini_api_key:
            return LLMInfo(provider="gemini", model=self.gemini_model, ready=True)
        return LLMInfo(
            provider="mock",
            model="—",
            ready=False,
            error=(
                "Не знайдено GEMINI_API_KEY. Без ключа система працює "
                "тільки у тестовому режимі (mock) і не може згенерувати "
                "справжній вірш. Додайте ключ у змінну середовища "
                "GEMINI_API_KEY, щоб увімкнути генерацію через Gemini."
            ),
        )

    @classmethod
    def from_env(cls) -> AppConfig:
        """Build config from environment variables."""
        def _bool(name: str, default: bool = False) -> bool:
            return _str(name, str(default)).lower() in ("1", "true", "yes", "y", "on")

        def _str(name: str, default: str = "") -> str:
            """Read a string env var, stripping whitespace and any trailing
            inline ``# comment`` that docker-compose's env_file parser
            leaves attached to the value. Protects against the common
            mistake ``LLM_PROVIDER=   # "" = auto`` copied from a template.
            """
            raw = os.getenv(name, default)
            if "#" in raw:
                raw = raw.split("#", 1)[0]
            return raw.strip()

        return cls(
            llm_provider=_str("LLM_PROVIDER"),
            gemini_api_key=_str("GEMINI_API_KEY"),
            gemini_model=_str("GEMINI_MODEL", "gemini-3.1-pro-preview"),
            gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.9")),
            gemini_max_tokens=int(os.getenv("GEMINI_MAX_TOKENS", "8192")),
            gemini_disable_thinking=_bool("GEMINI_DISABLE_THINKING", False),
            gemini_input_price_per_m=float(
                os.getenv(
                    "GEMINI_INPUT_PRICE_PER_M",
                    str(_GEMINI_DEFAULT_INPUT_PRICE_PER_M),
                )
            ),
            gemini_output_price_per_m=float(
                os.getenv(
                    "GEMINI_OUTPUT_PRICE_PER_M",
                    str(_GEMINI_DEFAULT_OUTPUT_PRICE_PER_M),
                )
            ),
            llm_reliability=LLMReliabilityConfig(
                timeout_sec=float(os.getenv("LLM_TIMEOUT_SEC", "120")),
                retry_max_attempts=int(os.getenv("LLM_RETRY_MAX_ATTEMPTS", "2")),
            ),
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
