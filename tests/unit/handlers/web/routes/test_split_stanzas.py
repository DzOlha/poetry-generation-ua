"""Unit tests for _split_stanzas helper in the detection route.

Cannot import directly from the route module (FastAPI dependency), so the
function is duplicated here for isolated testing. If the logic changes,
update both places.
"""
from __future__ import annotations


def _split_stanzas(poem_text: str, stanza_size: int) -> list[str]:
    """Exact copy of src.handlers.web.routes.detection._split_stanzas."""
    stanzas: list[str] = []
    current: list[str] = []
    has_blank_sep = False
    for line in poem_text.splitlines():
        if line.strip():
            current.append(line)
        else:
            if current:
                stanzas.append("\n".join(current))
                current = []
            has_blank_sep = True
    if current:
        stanzas.append("\n".join(current))

    if has_blank_sep or len(stanzas) != 1:
        return stanzas

    all_lines = [ln for ln in poem_text.splitlines() if ln.strip()]
    if len(all_lines) <= stanza_size:
        return stanzas

    chunks: list[str] = []
    for i in range(0, len(all_lines), stanza_size):
        chunk = all_lines[i : i + stanza_size]
        if chunk:
            chunks.append("\n".join(chunk))
    return chunks


class TestSplitByBlankLines:
    def test_two_stanzas_separated_by_blank_line(self) -> None:
        poem = "a\nb\nc\nd\n\ne\nf\ng\nh"
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 2
        assert len(stanzas[0].splitlines()) == 4
        assert len(stanzas[1].splitlines()) == 4

    def test_multiple_blank_lines_between_stanzas(self) -> None:
        poem = "a\nb\nc\nd\n\n\n\ne\nf\ng\nh"
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 2

    def test_three_stanzas(self) -> None:
        poem = "a\nb\n\nc\nd\n\ne\nf"
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 3

    def test_unequal_stanzas_by_blank_lines(self) -> None:
        poem = "a\nb\nc\n\nd\ne"
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 2
        assert len(stanzas[0].splitlines()) == 3
        assert len(stanzas[1].splitlines()) == 2


class TestSplitByStanzaSize:
    def test_8_lines_no_blanks_splits_into_two(self) -> None:
        poem = "\n".join(f"line {i}" for i in range(8))
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 2
        for s in stanzas:
            assert len(s.splitlines()) == 4

    def test_12_lines_splits_into_three(self) -> None:
        poem = "\n".join(f"line {i}" for i in range(12))
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 3

    def test_4_lines_stays_single_stanza(self) -> None:
        poem = "a\nb\nc\nd"
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 1

    def test_incomplete_last_chunk_kept(self) -> None:
        poem = "\n".join(f"line {i}" for i in range(6))
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 2
        assert len(stanzas[0].splitlines()) == 4
        assert len(stanzas[1].splitlines()) == 2

    def test_single_line_stays_single(self) -> None:
        stanzas = _split_stanzas("one line", stanza_size=4)
        assert len(stanzas) == 1


class TestEdgeCases:
    def test_empty_text(self) -> None:
        stanzas = _split_stanzas("", stanza_size=4)
        assert stanzas == []

    def test_only_blank_lines(self) -> None:
        stanzas = _split_stanzas("\n\n\n", stanza_size=4)
        assert stanzas == []

    def test_blank_lines_preferred_over_chunk_split(self) -> None:
        # Poem has blank line at line 3 (not at line 4), so blank-line split
        # takes precedence over stanza_size=4 chunking.
        poem = "a\nb\nc\n\nd\ne\nf\ng"
        stanzas = _split_stanzas(poem, stanza_size=4)
        assert len(stanzas) == 2
        assert len(stanzas[0].splitlines()) == 3  # a, b, c
        assert len(stanzas[1].splitlines()) == 4  # d, e, f, g
