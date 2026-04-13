"""Ukrainian weak-stress lexicon adapter."""
from __future__ import annotations

from src.domain.ports import IWeakStressLexicon

# Ukrainian function words treated as metrically unstressed.
WEAK_STRESS_WORDS: frozenset[str] = frozenset({
    # Prepositions
    "в", "у", "на", "з", "зі", "зо", "до", "від", "за", "під", "над",
    "між", "через", "по", "про", "без", "при", "для", "із", "об",
    "перед", "після", "навколо", "крізь", "поміж", "серед", "поза", "коло",
    # Conjunctions
    "і", "й", "та", "а", "але", "чи", "або", "якщо", "коли", "що", "як",
    "бо", "хоч", "хоча", "зате", "ані", "проте", "однак", "якби", "поки",
    "доки", "щоб", "аби", "ніж", "мов", "немов", "наче", "неначе", "мовби",
    "нібито", "тому", "отже", "адже", "тобто",
    # Particles
    "не", "ні", "б", "би", "же", "ж", "то", "хай", "нехай",
    "лише", "лиш", "тільки", "саме", "навіть", "ось", "он", "аж", "ще",
    "вже", "теж", "також",
    # Personal pronouns
    "я", "ти", "він", "вона", "воно", "ми", "ви", "вони",
    "мене", "тебе", "його", "її", "нас", "вас", "них",
    # Possessive / demonstrative
    "мій", "моя", "моє", "мої", "твій", "твоя", "твоє", "твої",
    "свій", "своя", "своє", "свої", "це", "те",
})


class UkrainianWeakStressLexicon(IWeakStressLexicon):
    """IWeakStressLexicon implementation backed by a frozen Ukrainian word set."""

    def is_weak(self, word: str) -> bool:
        return word.lower() in WEAK_STRESS_WORDS
