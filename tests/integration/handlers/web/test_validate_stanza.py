"""Integration test: per-stanza validation returns meter and rhyme accuracy.

Exercises _validate_stanza logic indirectly through the real composition
root to verify that both meter_accuracy and rhyme_accuracy are present
in the result.
"""
from __future__ import annotations

import pytest

from src.composition_root import build_poetry_service
from src.config import AppConfig
from src.domain.models import MeterSpec, RhymeScheme, ValidationRequest

_QUATRAIN = (
    "Реве та стогне Дніпр широкий\n"
    "Сердитий вітер завива\n"
    "Додолу верби гне високі\n"
    "Горами хвилю підійма"
)


@pytest.fixture(scope="session")
def _poetry_service():
    config = AppConfig(offline_embedder=True)
    return build_poetry_service(config)


class TestValidateStanzaIntegration:
    @pytest.mark.integration
    def test_validation_returns_meter_accuracy(self, _poetry_service) -> None:
        validation = _poetry_service.validate(ValidationRequest(
            poem_text=_QUATRAIN,
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        ))
        assert isinstance(validation.meter.accuracy, float)
        assert 0.0 <= validation.meter.accuracy <= 1.0

    @pytest.mark.integration
    def test_validation_returns_rhyme_accuracy(self, _poetry_service) -> None:
        validation = _poetry_service.validate(ValidationRequest(
            poem_text=_QUATRAIN,
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        ))
        assert isinstance(validation.rhyme.accuracy, float)
        assert 0.0 <= validation.rhyme.accuracy <= 1.0

    @pytest.mark.integration
    def test_line_results_cover_all_lines(self, _poetry_service) -> None:
        validation = _poetry_service.validate(ValidationRequest(
            poem_text=_QUATRAIN,
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        ))
        assert len(validation.meter.line_results) == 4

    @pytest.mark.integration
    def test_two_stanza_poem_rhyme_pairs_both_stanzas(self, _poetry_service) -> None:
        two_stanzas = _QUATRAIN + "\n" + _QUATRAIN
        validation = _poetry_service.validate(ValidationRequest(
            poem_text=two_stanzas,
            meter=MeterSpec(name="ямб", foot_count=4),
            rhyme=RhymeScheme(pattern="ABAB"),
        ))
        # Rhyme validator now checks all stanzas, so pair_results should
        # cover both stanzas (4 pairs for 8 lines with ABAB).
        assert len(validation.rhyme.pair_results) == 4
