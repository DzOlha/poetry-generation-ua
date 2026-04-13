"""Contract tests wiring each IMeterValidator through IMeterValidatorContract."""
from __future__ import annotations

import pytest

from src.domain.ports import IMeterValidator
from src.infrastructure.text import UkrainianTextProcessor
from src.infrastructure.validators.meter import (
    DefaultLineFeedbackBuilder,
    PatternMeterValidator,
    UkrainianProsodyAnalyzer,
)
from src.infrastructure.validators.meter.bsp_algorithm import BSPAlgorithm
from src.infrastructure.validators.meter.bsp_validator import BSPMeterValidator
from tests.contracts.meter_validator_contract import IMeterValidatorContract


class TestPatternMeterValidatorContract(IMeterValidatorContract):
    @pytest.fixture
    def validator(
        self,
        prosody_analyzer: UkrainianProsodyAnalyzer,
        text_processor: UkrainianTextProcessor,
        line_feedback_builder: DefaultLineFeedbackBuilder,
    ) -> IMeterValidator:
        return PatternMeterValidator(
            prosody=prosody_analyzer,
            text_processor=text_processor,
            feedback_builder=line_feedback_builder,
        )


class TestBSPMeterValidatorContract(IMeterValidatorContract):
    @pytest.fixture
    def validator(
        self,
        prosody_analyzer: UkrainianProsodyAnalyzer,
        text_processor: UkrainianTextProcessor,
        line_feedback_builder: DefaultLineFeedbackBuilder,
    ) -> IMeterValidator:
        return BSPMeterValidator(
            prosody=prosody_analyzer,
            text_processor=text_processor,
            feedback_builder=line_feedback_builder,
            bsp_algorithm=BSPAlgorithm(),
        )
