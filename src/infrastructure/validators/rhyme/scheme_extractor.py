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

        For schemes with N letters repeated across a stanza (e.g. ABAB for
        a 4-line stanza), only stanza-level pairs within the first 4 lines are
        returned.  Multi-stanza support is left to the caller by invoking this
        method per stanza or by passing a repeated pattern.

        Raises:
            ValueError: If the scheme is not recognised and has no repeated letters.
        """
        s = scheme.strip().upper()

        # Fast paths for the four canonical schemes
        if s == "ABAB":
            return [(0, 2), (1, 3)] if n_lines >= 4 else []
        if s == "AABB":
            return [(0, 1), (2, 3)] if n_lines >= 4 else []
        if s == "ABBA":
            return [(0, 3), (1, 2)] if n_lines >= 4 else []
        if s == "AAAA":
            return [(i, j) for i in range(n_lines) for j in range(i + 1, n_lines)]

        # General algorithm: group lines by their scheme letter
        groups: dict[str, list[int]] = {}
        for line_idx, letter in enumerate(s):
            if line_idx >= n_lines:
                break
            groups.setdefault(letter, []).append(line_idx)

        pairs: list[tuple[int, int]] = []
        for indices in groups.values():
            if len(indices) >= 2:
                pairs.extend(
                    (indices[i], indices[j])
                    for i in range(len(indices))
                    for j in range(i + 1, len(indices))
                )

        if not pairs:
            raise UnsupportedConfigError(f"Unsupported rhyme scheme: '{scheme}'")

        return sorted(pairs)
