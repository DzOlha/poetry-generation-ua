import re
from dataclasses import dataclass


VOWELS_UA = "аеєиіїоуюя"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_words_ua(text: str) -> list[str]:
    return re.findall(r"[а-яіїєґʼ'-]+", text.lower())


def count_syllables_ua(word: str) -> int:
    return sum(1 for c in word.lower() if c in VOWELS_UA)


def split_nonempty_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


@dataclass(frozen=True)
class LineTokens:
    line: str
    words: list[str]
    syllables_per_word: list[int]


def tokenize_line_ua(line: str) -> LineTokens:
    words = extract_words_ua(line)
    syllables = [count_syllables_ua(w) for w in words]
    return LineTokens(line=line, words=words, syllables_per_word=syllables)
