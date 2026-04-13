"""Validation sub-container.

Owns meter validators (pattern + BSP), rhyme validator, rhyme pair
analyser, rhyme scheme extractor, poem validator facade, and BSP
algorithm. Depends only on `PrimitivesSubContainer` and `AppConfig`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import ValidationConfig
from src.domain.ports import IFeedbackFormatter, IMeterValidator, IPoemValidator, IRhymeValidator
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.feedback import UkrainianFeedbackFormatter
from src.infrastructure.validators import CompositePoemValidator
from src.infrastructure.validators.meter import (
    BSPAlgorithm,
    BSPMeterValidator,
    PatternMeterValidator,
)
from src.infrastructure.validators.rhyme.pair_analyzer import PhoneticRhymePairAnalyzer
from src.infrastructure.validators.rhyme.phonetic_validator import PhoneticRhymeValidator
from src.infrastructure.validators.rhyme.scheme_extractor import StandardRhymeSchemeExtractor

if TYPE_CHECKING:
    from src.composition_root import Container


class ValidationSubContainer:
    """Meter + rhyme validators and the composite poem validator façade."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def bsp_algorithm(self) -> BSPAlgorithm:
        """BSP math engine wired from `ValidationConfig` weights."""
        def factory() -> BSPAlgorithm:
            vc: ValidationConfig = self._parent.config.validation
            return BSPAlgorithm(
                alternation_weight=vc.bsp_alternation_weight,
                variation_weight=vc.bsp_variation_weight,
                stability_weight=vc.bsp_stability_weight,
                balance_weight=vc.bsp_balance_weight,
            )

        return self._parent._get(CacheKey.BSP_ALGORITHM, factory)

    def bsp_meter_validator(self) -> IMeterValidator:
        """Alternative BSP-based meter validator — opt-in via `meter_validator()`."""
        def factory() -> IMeterValidator:
            vc: ValidationConfig = self._parent.config.validation
            prims = self._parent.primitives
            return BSPMeterValidator(
                prosody=prims.prosody(),
                text_processor=prims.text_processor(),
                feedback_builder=prims.line_feedback_builder(),
                bsp_algorithm=self.bsp_algorithm(),
                score_threshold=vc.bsp_score_threshold,
                allowed_mismatches=vc.meter_allowed_mismatches,
            )

        return self._parent._get(CacheKey.BSP_METER_VALIDATOR, factory)

    def meter_validator(self) -> IMeterValidator:
        def factory() -> IMeterValidator:
            vc: ValidationConfig = self._parent.config.validation
            prims = self._parent.primitives
            return PatternMeterValidator(
                prosody=prims.prosody(),
                text_processor=prims.text_processor(),
                feedback_builder=prims.line_feedback_builder(),
                allowed_mismatches=vc.meter_allowed_mismatches,
            )

        return self._parent._get(CacheKey.METER_VALIDATOR, factory)

    def rhyme_scheme_extractor(self) -> StandardRhymeSchemeExtractor:
        return self._parent._get(
            CacheKey.RHYME_SCHEME_EXTRACTOR, StandardRhymeSchemeExtractor,
        )

    def rhyme_pair_analyzer(self) -> PhoneticRhymePairAnalyzer:
        return self._parent._get(
            CacheKey.RHYME_PAIR_ANALYZER,
            lambda: PhoneticRhymePairAnalyzer(
                stress_resolver=self._parent.primitives.stress_resolver(),
                transcriber=self._parent.primitives.phonetic_transcriber(),
                string_similarity=self._parent.primitives.string_similarity(),
                syllable_counter=self._parent.primitives.syllable_counter(),
            ),
        )

    def rhyme_validator(self) -> IRhymeValidator:
        def factory() -> IRhymeValidator:
            vc: ValidationConfig = self._parent.config.validation
            tp = self._parent.primitives.text_processor()
            return PhoneticRhymeValidator(
                line_splitter=tp,
                tokenizer=tp,
                scheme_extractor=self.rhyme_scheme_extractor(),
                pair_analyzer=self.rhyme_pair_analyzer(),
                threshold=vc.rhyme_threshold,
            )

        return self._parent._get(CacheKey.RHYME_VALIDATOR, factory)

    def poem_validator(self) -> IPoemValidator:
        return self._parent._get(
            CacheKey.POEM_VALIDATOR,
            lambda: CompositePoemValidator(
                meter_validator=self.meter_validator(),
                rhyme_validator=self.rhyme_validator(),
            ),
        )

    def feedback_formatter(self) -> IFeedbackFormatter:
        return self._parent._get(CacheKey.FEEDBACK_FORMATTER, UkrainianFeedbackFormatter)
