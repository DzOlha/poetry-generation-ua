"""Tests for UkrainianIpaTranscriber (formerly free-function transcriber)."""
from __future__ import annotations

import pytest

from src.infrastructure.phonetics.ukrainian_ipa_transcriber import UkrainianIpaTranscriber


@pytest.fixture
def transcriber() -> UkrainianIpaTranscriber:
    return UkrainianIpaTranscriber()


class TestTranscribeUa:
    @pytest.mark.parametrize(
        "word, expected",
        [
            ("ліс", "lis"),
            ("весна", "vesna"),
            ("сонце", "sontse"),
            ("щастя", "ʃtʃastja"),
        ],
    )
    def test_basic_transcriptions(
        self, transcriber: UkrainianIpaTranscriber, word: str, expected: str,
    ):
        assert transcriber.transcribe(word) == expected

    def test_empty_string(self, transcriber: UkrainianIpaTranscriber):
        assert transcriber.transcribe("") == ""

    def test_soft_sign_removed(self, transcriber: UkrainianIpaTranscriber):
        assert "ь" not in transcriber.transcribe("день")

    def test_apostrophe_removed(self, transcriber: UkrainianIpaTranscriber):
        assert "'" not in transcriber.transcribe("пам'ять")


class TestVowelPositions:
    def test_simple(self, transcriber: UkrainianIpaTranscriber):
        positions = transcriber.vowel_positions("vesna")
        assert positions == [1, 4]  # v-e-s-n-a -> e at 1, a at 4

    def test_no_vowels(self, transcriber: UkrainianIpaTranscriber):
        assert transcriber.vowel_positions("bcd") == []


class TestRhymePartFromStress:
    def test_last_syllable_stress(self, transcriber: UkrainianIpaTranscriber):
        part = transcriber.rhyme_part("весна", 1)
        assert part.startswith(("a", "na"))

    def test_first_syllable_stress(self, transcriber: UkrainianIpaTranscriber):
        assert len(transcriber.rhyme_part("ліс", 0)) > 0

    def test_empty_word(self, transcriber: UkrainianIpaTranscriber):
        assert transcriber.rhyme_part("", 0) == ""

    def test_single_vowel_word(self, transcriber: UkrainianIpaTranscriber):
        assert len(transcriber.rhyme_part("я", 0)) > 0
