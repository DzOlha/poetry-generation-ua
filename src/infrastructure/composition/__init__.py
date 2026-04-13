"""Composition sub-containers.

Each sub-container owns one logical slice of the DI graph (primitives,
validation, generation, metrics, evaluation). The top-level `Container`
in `src.composition_root` composes them and delegates public accessors,
so callers still see a single façade but the wiring is no longer a 578-
line monolith.

Sub-containers share the parent container's `_cache` dict — memoisation
stays uniform across the whole graph. Cross-sub-container dependencies
are expressed by calling the parent (e.g. `self._parent.validation.meter_validator()`).
"""
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.composition.detection import DetectionSubContainer
from src.infrastructure.composition.evaluation import EvaluationSubContainer
from src.infrastructure.composition.generation import GenerationSubContainer
from src.infrastructure.composition.metrics import MetricsSubContainer
from src.infrastructure.composition.primitives import PrimitivesSubContainer
from src.infrastructure.composition.validation import ValidationSubContainer

__all__ = [
    "CacheKey",
    "DetectionSubContainer",
    "EvaluationSubContainer",
    "GenerationSubContainer",
    "MetricsSubContainer",
    "PrimitivesSubContainer",
    "ValidationSubContainer",
]
