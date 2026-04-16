"""Validator fixtures — meter, rhyme, composite validators."""
from __future__ import annotations

import pytest

from src.domain.ports import IStressResolver
from src.infrastructure.meter import (
    DefaultSyllableFlagStrategy,
    UkrainianMeterTemplateProvider,
    UkrainianWeakStressLexicon,
)
from src.infrastructure.phonetics import UkrainianIpaTranscriber
from src.infrastructure.stress import UkrainianSyllableCounter
from src.infrastructure.text import LevenshteinSimilarity, UkrainianTextProcessor
from src.infrastructure.validators import CompositePoemValidator
from src.infrastructure.validators.meter import (
    DefaultLineFeedbackBuilder,
    PatternMeterValidator,
    UkrainianProsodyAnalyzer,
)
from src.infrastructure.validators.rhyme.pair_analyzer import PhoneticRhymePairAnalyzer
from src.infrastructure.validators.rhyme.phonetic_validator import PhoneticRhymeValidator
from src.infrastructure.validators.rhyme.scheme_extractor import StandardRhymeSchemeExtractor


@pytest.fixture(scope="session")
def prosody_analyzer(
    meter_template_provider: UkrainianMeterTemplateProvider,
    syllable_flag_strategy: DefaultSyllableFlagStrategy,
    stress_resolver: IStressResolver,
    weak_stress_lexicon: UkrainianWeakStressLexicon,
) -> UkrainianProsodyAnalyzer:
    return UkrainianProsodyAnalyzer(
        template_provider=meter_template_provider,
        flag_strategy=syllable_flag_strategy,
        stress_resolver=stress_resolver,
        weak_stress_lexicon=weak_stress_lexicon,
    )


@pytest.fixture(scope="session")
def line_feedback_builder(
    meter_template_provider: UkrainianMeterTemplateProvider,
) -> DefaultLineFeedbackBuilder:
    return DefaultLineFeedbackBuilder(template_provider=meter_template_provider)


@pytest.fixture(scope="session")
def meter_validator(
    prosody_analyzer: UkrainianProsodyAnalyzer,
    text_processor: UkrainianTextProcessor,
    line_feedback_builder: DefaultLineFeedbackBuilder,
) -> PatternMeterValidator:
    return PatternMeterValidator(
        prosody=prosody_analyzer,
        text_processor=text_processor,
        feedback_builder=line_feedback_builder,
    )


@pytest.fixture(scope="session")
def rhyme_pair_analyzer(
    stress_resolver: IStressResolver,
    phonetic_transcriber: UkrainianIpaTranscriber,
    syllable_counter: UkrainianSyllableCounter,
    text_processor: UkrainianTextProcessor,
) -> PhoneticRhymePairAnalyzer:
    return PhoneticRhymePairAnalyzer(
        stress_resolver=stress_resolver,
        transcriber=phonetic_transcriber,
        string_similarity=LevenshteinSimilarity(),
        syllable_counter=syllable_counter,
    )


@pytest.fixture(scope="session")
def rhyme_validator(
    text_processor: UkrainianTextProcessor,
    rhyme_pair_analyzer: PhoneticRhymePairAnalyzer,
) -> PhoneticRhymeValidator:
    return PhoneticRhymeValidator(
        line_splitter=text_processor,
        tokenizer=text_processor,
        scheme_extractor=StandardRhymeSchemeExtractor(),
        pair_analyzer=rhyme_pair_analyzer,
    )


@pytest.fixture(scope="session")
def poem_validator(
    meter_validator: PatternMeterValidator,
    rhyme_validator: PhoneticRhymeValidator,
) -> CompositePoemValidator:
    return CompositePoemValidator(
        meter_validator=meter_validator,
        rhyme_validator=rhyme_validator,
    )
