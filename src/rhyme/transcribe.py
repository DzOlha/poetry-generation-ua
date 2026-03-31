from __future__ import annotations

from src.utils.text import VOWELS_UA

_UA_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "ɦ",
    "ґ": "g",
    "д": "d",
    "е": "e",
    "є": "je",
    "ж": "ʒ",
    "з": "z",
    "и": "ɪ",
    "і": "i",
    "ї": "ji",
    "й": "j",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "x",
    "ц": "ts",
    "ч": "tʃ",
    "ш": "ʃ",
    "щ": "ʃtʃ",
    "ь": "",
    "ю": "ju",
    "я": "ja",
    "'": "",
    "ʼ": "",
    "-": "",
}


def transcribe_ua(word: str) -> str:
    w = word.lower()
    out: list[str] = []
    i = 0
    while i < len(w):
        ch = w[i]
        out.append(_UA_MAP.get(ch, ""))
        i += 1
    return "".join(out)


def vowel_positions_in_ipa(ipa: str) -> list[int]:
    vowels = set("aeiouɪ")
    return [i for i, ch in enumerate(ipa) if ch in vowels]


def rhyme_part_from_stress(word: str, stress_syllable_idx_0based: int) -> str:
    ipa = transcribe_ua(word)
    vpos = vowel_positions_in_ipa(ipa)
    if not vpos:
        return ipa
    stress_syllable_idx_0based = min(max(0, stress_syllable_idx_0based), len(vpos) - 1)
    return ipa[vpos[stress_syllable_idx_0based] :]


def is_ua_vowel(ch: str) -> bool:
    return ch.lower() in VOWELS_UA
