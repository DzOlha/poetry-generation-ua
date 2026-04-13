"""Primitives sub-container.

Holds every low-level leaf adapter: text processor, stress dictionary,
syllable counter, stress resolver, phonetic transcriber, meter templates,
weak-stress lexicon, syllable flag strategy, prosody analyser, line
feedback builder, meter canonicaliser.

These are the foundation that every higher sub-container depends on.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.ports import (
    ILineFeedbackBuilder,
    IMeterCanonicalizer,
    IPhoneticTranscriber,
    IStressDictionary,
    IStressResolver,
    IStringSimilarity,
    ISyllableCounter,
    ITextProcessor,
)
from src.domain.ports.prosody import (
    IMeterTemplateProvider,
    IProsodyAnalyzer,
    ISyllableFlagStrategy,
    IWeakStressLexicon,
)
from src.infrastructure.composition.cache_keys import CacheKey
from src.infrastructure.meter import (
    DefaultSyllableFlagStrategy,
    UkrainianMeterCanonicalizer,
    UkrainianMeterTemplateProvider,
    UkrainianWeakStressLexicon,
)
from src.infrastructure.phonetics import UkrainianIpaTranscriber
from src.infrastructure.stress import (
    PenultimateFallbackStressResolver,
    UkrainianStressDict,
    UkrainianSyllableCounter,
)
from src.infrastructure.text import LevenshteinSimilarity, UkrainianTextProcessor
from src.infrastructure.validators.meter import (
    DefaultLineFeedbackBuilder,
    UkrainianProsodyAnalyzer,
)

if TYPE_CHECKING:
    from src.composition_root import Container


class PrimitivesSubContainer:
    """Text / stress / phonetics / meter primitives."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent

    def text_processor(self) -> ITextProcessor:
        return self._parent._get(CacheKey.TEXT_PROCESSOR, UkrainianTextProcessor)

    def string_similarity(self) -> IStringSimilarity:
        return self._parent._get(CacheKey.STRING_SIMILARITY, LevenshteinSimilarity)

    def stress_dict(self) -> IStressDictionary:
        return self._parent._get(
            CacheKey.STRESS_DICT,
            lambda: UkrainianStressDict(
                logger=self._parent.logger, on_ambiguity="first",
            ),
        )

    def syllable_counter(self) -> ISyllableCounter:
        return self._parent._get(CacheKey.SYLLABLE_COUNTER, UkrainianSyllableCounter)

    def stress_resolver(self) -> IStressResolver:
        return self._parent._get(
            CacheKey.STRESS_RESOLVER,
            lambda: PenultimateFallbackStressResolver(
                stress_dictionary=self.stress_dict(),
                syllable_counter=self.syllable_counter(),
            ),
        )

    def phonetic_transcriber(self) -> IPhoneticTranscriber:
        return self._parent._get(CacheKey.PHONETIC_TRANSCRIBER, UkrainianIpaTranscriber)

    def meter_canonicalizer(self) -> IMeterCanonicalizer:
        return self._parent._get(CacheKey.METER_CANONICALIZER, UkrainianMeterCanonicalizer)

    def meter_template_provider(self) -> IMeterTemplateProvider:
        return self._parent._get(
            CacheKey.METER_TEMPLATE_PROVIDER, UkrainianMeterTemplateProvider,
        )

    def weak_stress_lexicon(self) -> IWeakStressLexicon:
        return self._parent._get(CacheKey.WEAK_STRESS_LEXICON, UkrainianWeakStressLexicon)

    def syllable_flag_strategy(self) -> ISyllableFlagStrategy:
        return self._parent._get(
            CacheKey.SYLLABLE_FLAG_STRATEGY,
            lambda: DefaultSyllableFlagStrategy(
                weak_stress_lexicon=self.weak_stress_lexicon(),
            ),
        )

    def prosody(self) -> IProsodyAnalyzer:
        return self._parent._get(
            CacheKey.PROSODY,
            lambda: UkrainianProsodyAnalyzer(
                template_provider=self.meter_template_provider(),
                flag_strategy=self.syllable_flag_strategy(),
                stress_resolver=self.stress_resolver(),
            ),
        )

    def line_feedback_builder(self) -> ILineFeedbackBuilder:
        return self._parent._get(
            CacheKey.LINE_FEEDBACK_BUILDER, DefaultLineFeedbackBuilder,
        )
