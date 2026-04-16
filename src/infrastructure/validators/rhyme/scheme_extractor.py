"""Rhyme-scheme extractor — maps a scheme pattern to concrete line-pair indices.

StandardRhymeSchemeExtractor supports the four canonical Ukrainian poetry
rhyme schemes: ABAB, AABB, ABBA, AAAA.

Adding a new scheme (e.g. ABCABC) means implementing IRhymeSchemeExtractor
or extending this class — PhoneticRhymeValidator never needs to change.
"""
from __future__ import annotations

from src.domain.errors import UnsupportedConfigError
from src.domain.ports import IRhymeSchemeExtractor


class StandardRhymeSchemeExtractor(IRhymeSchemeExtractor):
    """Extracts rhyming line-pair indices for ABAB / AABB / ABBA / AAAA schemes.

    The general-purpose algorithm treats the scheme string as a letter pattern:
    lines sharing the same letter must rhyme.  Pairs are emitted in order so
    that validation feedback is deterministic.
    """

    def extract_pairs(self, scheme: str, n_lines: int) -> list[tuple[int, int]]:
        """Return 0-based (a_idx, b_idx) pairs that must rhyme for this scheme.

        The scheme pattern is treated as a per-stanza template and repeated
        across all stanzas of the poem.  For example, ABAB with 8 lines
        yields pairs (0,2), (1,3), (4,6), (5,7).

        Raises:
            UnsupportedConfigError: If the scheme has no repeated letters.
        """
        s = scheme.strip().upper()
        stanza_size = len(s)

        if stanza_size == 0 or n_lines < stanza_size:
            return []

        # Build per-stanza pairs from the letter pattern
        groups: dict[str, list[int]] = {}
        for idx, letter in enumerate(s):
            groups.setdefault(letter, []).append(idx)

        stanza_pairs: list[tuple[int, int]] = []
        for indices in groups.values():
            if len(indices) >= 2:
                stanza_pairs.extend(
                    (indices[i], indices[j])
                    for i in range(len(indices))
                    for j in range(i + 1, len(indices))
                )
        stanza_pairs.sort()

        if not stanza_pairs:
            raise UnsupportedConfigError(f"Unsupported rhyme scheme: '{scheme}'")

        # Repeat stanza pairs across all complete stanzas
        all_pairs: list[tuple[int, int]] = []
        for stanza_start in range(0, n_lines, stanza_size):
            if stanza_start + stanza_size > n_lines:
                break
            for a, b in stanza_pairs:
                all_pairs.append((stanza_start + a, stanza_start + b))

        return all_pairs
