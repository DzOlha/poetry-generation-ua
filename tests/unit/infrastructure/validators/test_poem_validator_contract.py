"""Contract conformance test for CompositePoemValidator."""
from __future__ import annotations

import pytest

from src.domain.ports import IMeterValidator, IPoemValidator, IRhymeValidator
from src.infrastructure.validators import CompositePoemValidator
from tests.contracts.poem_validator_contract import IPoemValidatorContract


class TestCompositePoemValidatorContract(IPoemValidatorContract):
    @pytest.fixture(autouse=True)
    def _inject_validators(
        self,
        meter_validator: IMeterValidator,
        rhyme_validator: IRhymeValidator,
    ) -> None:
        self._meter_validator = meter_validator
        self._rhyme_validator = rhyme_validator

    def _make_validator(self) -> IPoemValidator:
        return CompositePoemValidator(
            meter_validator=self._meter_validator,
            rhyme_validator=self._rhyme_validator,
        )
