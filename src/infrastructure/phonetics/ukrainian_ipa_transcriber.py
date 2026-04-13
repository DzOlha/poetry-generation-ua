"""Ukrainian → IPA transcriber implementing IPhoneticTranscriber.

The character map and vowel set used to live as module-level free
functions in `validators/rhyme/transcriber.py`. They are now encapsulated
in this class so the role (phonetic transcription) is injected via DI and
swappable for a different language or a more accurate phoneme model.
"""
from __future__ import annotations

from src.domain.ports import IPhoneticTranscriber

# ---------------------------------------------------------------------------
# Ukrainian → IPA character mapping
# ---------------------------------------------------------------------------

_UA_MAP: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "ɦ", "ґ": "g",
    "д": "d", "е": "e", "є": "je", "ж": "ʒ", "з": "z",
    "и": "ɪ", "і": "i", "ї": "ji", "й": "j", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ц": "ts", "ч": "tʃ", "ш": "ʃ", "щ": "ʃtʃ",
    "ь": "", "ю": "ju", "я": "ja", "'": "", "ʼ": "", "-": "",
}

_IPA_VOWELS: frozenset[str] = frozenset("aeiouɪ")


class UkrainianIpaTranscriber(IPhoneticTranscriber):
    """IPhoneticTranscriber for Ukrainian (rule-based IPA approximation)."""

    def transcribe(self, word: str) -> str:
        return "".join(_UA_MAP.get(ch, "") for ch in word.lower())

    def vowel_positions(self, transcription: str) -> list[int]:
        return [i for i, ch in enumerate(transcription) if ch in _IPA_VOWELS]

    def rhyme_part(self, word: str, stress_syllable_idx: int) -> str:
        ipa = self.transcribe(word)
        vpos = self.vowel_positions(ipa)
        if not vpos:
            return ipa
        idx = min(max(0, stress_syllable_idx), len(vpos) - 1)
        return ipa[vpos[idx]:]
