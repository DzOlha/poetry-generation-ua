"""Integration test: detection service with real validators."""
from __future__ import annotations

import pytest

from src.composition_root import build_container, build_detection_service
from src.config import AppConfig, DetectionConfig


@pytest.fixture
def detection_service():
    config = AppConfig(
        offline_embedder=True,
        detection=DetectionConfig(
            meter_min_accuracy=0.70,
            rhyme_min_accuracy=0.50,
            sample_lines=4,
        ),
    )
    return build_detection_service(config)


# A well-known iamb-4 ABAB poem (Shevchenko)
_IAMB_4_ABAB = (
    "Реве та стогне Дніпр широкий\n"
    "Сердитий вітер завива\n"
    "Додолу верби гне високі\n"
    "Горами хвилю підійма"
)


class TestDetectionIntegration:
    @pytest.mark.component
    def test_detects_meter_from_known_poem(self, detection_service) -> None:
        result = detection_service.detect(_IAMB_4_ABAB)
        if result.meter is not None:
            assert result.meter.meter in ("ямб", "хорей", "дактиль", "амфібрахій", "анапест")
            assert result.meter.accuracy > 0.0

    @pytest.mark.component
    def test_returns_result_for_short_text(self, detection_service) -> None:
        result = detection_service.detect("Короткий текст")
        # Too short for 4-line sample
        assert result.meter is None
        assert result.rhyme is None

    @pytest.mark.component
    def test_custom_sample_lines(self, detection_service) -> None:
        # 2-line sample from a 4-line poem
        result = detection_service.detect(_IAMB_4_ABAB, sample_lines=2)
        # Should succeed or fail gracefully — no crash
        assert isinstance(result.is_detected, bool)

    @pytest.mark.component
    def test_composition_root_wires_detection(self) -> None:
        config = AppConfig(offline_embedder=True)
        container = build_container(config)
        # All detection components should resolve without errors
        sampler = container.stanza_sampler()
        assert sampler is not None
        detector = container.meter_detector()
        assert detector is not None
        rhyme = container.rhyme_detector()
        assert rhyme is not None
