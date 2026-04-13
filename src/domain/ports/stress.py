"""Stress and phonetics ports."""
from __future__ import annotations

from abc import ABC, abstractmethod


class IStressDictionary(ABC):
    """Assigns stress positions to words in a given language."""

    @abstractmethod
    def get_stress_index(self, word: str) -> int | None: ...


class ISyllableCounter(ABC):
    """Counts syllables in a single word for a specific language."""

    @abstractmethod
    def count(self, word: str) -> int: ...


class IStressResolver(ABC):
    """Resolves a definite stressed-vowel index for any word (dict + fallback)."""

    @abstractmethod
    def resolve(self, word: str) -> int: ...


class IPhoneticTranscriber(ABC):
    """Converts language-specific text into a phonetic representation."""

    @abstractmethod
    def transcribe(self, word: str) -> str: ...

    @abstractmethod
    def vowel_positions(self, transcription: str) -> list[int]: ...

    @abstractmethod
    def rhyme_part(self, word: str, stress_syllable_idx: int) -> str: ...


class IMeterCanonicalizer(ABC):
    """Canonicalises meter-name strings to a stable comparable form."""

    @abstractmethod
    def canonicalize(self, name: str) -> str: ...
