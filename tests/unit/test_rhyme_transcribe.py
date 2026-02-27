from __future__ import annotations

import pytest

from src.rhyme.transcribe import (
    rhyme_part_from_stress,
    transcribe_ua,
    vowel_positions_in_ipa,
)


class TestTranscribeUa:
    @pytest.mark.parametrize(
        "word, expected_contains",
        [
            ("ліс", "lis"),
            ("весна", "vesna"),
            ("сонце", "sontse"),
            ("щастя", "ʃtʃastja"),
        ],
    )
    def test_basic_transcriptions(self, word: str, expected_contains: str):
        ipa = transcribe_ua(word)
        assert ipa == expected_contains

    def test_empty_string(self):
        assert transcribe_ua("") == ""

    def test_soft_sign_removed(self):
        ipa = transcribe_ua("день")
        assert "ь" not in ipa

    def test_apostrophe_removed(self):
        ipa = transcribe_ua("пам'ять")
        assert "'" not in ipa


class TestVowelPositions:
    def test_simple(self):
        ipa = "vesna"
        positions = vowel_positions_in_ipa(ipa)
        assert positions == [1, 4]  # v-e-s-n-a -> e at 1, a at 4

    def test_no_vowels(self):
        assert vowel_positions_in_ipa("bcd") == []


class TestRhymePartFromStress:
    def test_last_syllable_stress(self):
        part = rhyme_part_from_stress("весна", 1)
        assert part.startswith("a") or part.startswith("na")

    def test_first_syllable_stress(self):
        part = rhyme_part_from_stress("ліс", 0)
        assert len(part) > 0

    def test_empty_word(self):
        part = rhyme_part_from_stress("", 0)
        assert part == ""

    def test_single_vowel_word(self):
        part = rhyme_part_from_stress("я", 0)
        assert len(part) > 0
