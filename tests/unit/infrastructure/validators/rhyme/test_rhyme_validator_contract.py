"""Contract tests wiring PhoneticRhymeValidator through IRhymeValidatorContract."""
from __future__ import annotations

import pytest

from src.domain.ports import IRhymeValidator
from src.infrastructure.text import UkrainianTextProcessor
from src.infrastructure.validators.rhyme.pair_analyzer import PhoneticRhymePairAnalyzer
from src.infrastructure.validators.rhyme.phonetic_validator import PhoneticRhymeValidator
from src.infrastructure.validators.rhyme.scheme_extractor import StandardRhymeSchemeExtractor
from tests.contracts.rhyme_validator_contract import IRhymeValidatorContract


class TestPhoneticRhymeValidatorContract(IRhymeValidatorContract):
    @pytest.fixture
    def validator(
        self,
        text_processor: UkrainianTextProcessor,
        rhyme_pair_analyzer: PhoneticRhymePairAnalyzer,
    ) -> IRhymeValidator:
        return PhoneticRhymeValidator(
            line_splitter=text_processor,
            tokenizer=text_processor,
            scheme_extractor=StandardRhymeSchemeExtractor(),
            pair_analyzer=rhyme_pair_analyzer,
        )
