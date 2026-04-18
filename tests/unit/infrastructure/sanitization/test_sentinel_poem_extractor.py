"""Tests for `SentinelPoemExtractor`."""
from __future__ import annotations

import pytest

from src.infrastructure.sanitization import SentinelPoemExtractor


@pytest.fixture
def extractor() -> SentinelPoemExtractor:
    return SentinelPoemExtractor()


class TestHappyPath:
    def test_extracts_block_between_tags(self, extractor: SentinelPoemExtractor) -> None:
        raw = (
            "Let me think about dactyl meter...\n"
            "<POEM>\n"
            "Тихо спить у місті ніч\n"
            "Ліхтарі горять в імлі\n"
            "</POEM>\n"
        )
        assert extractor.extract(raw) == "Тихо спить у місті ніч\nЛіхтарі горять в імлі\n"

    def test_tag_matching_is_case_insensitive(
        self, extractor: SentinelPoemExtractor,
    ) -> None:
        raw = "reasoning\n<poem>\nТихо спить\n</Poem>\n"
        assert extractor.extract(raw) == "Тихо спить\n"

    def test_empty_input_passes_through(self, extractor: SentinelPoemExtractor) -> None:
        assert extractor.extract("") == ""


class TestMalformedEnvelopes:
    def test_missing_tags_returns_input_unchanged(
        self, extractor: SentinelPoemExtractor,
    ) -> None:
        raw = "Тихо спить\nЛіхтарі горять\n"
        assert extractor.extract(raw) == raw

    def test_open_tag_without_close_salvages_tail(
        self, extractor: SentinelPoemExtractor,
    ) -> None:
        raw = "CoT here\n<POEM>\nТихо спить\nЛіхтарі\n"
        assert extractor.extract(raw) == "Тихо спить\nЛіхтарі\n"

    def test_empty_block_falls_back_to_input(
        self, extractor: SentinelPoemExtractor,
    ) -> None:
        raw = "Let me think.\n<POEM></POEM>\nПотім щось ще.\n"
        # Empty block → caller (sanitizer) still needs to see something.
        assert extractor.extract(raw) == raw

    def test_multiple_blocks_takes_last(self, extractor: SentinelPoemExtractor) -> None:
        # Models sometimes revise mid-CoT — the last committed block wins.
        raw = (
            "<POEM>\nПерша спроба\n</POEM>\n"
            "wait, rewriting\n"
            "<POEM>\nФінальний варіант\n</POEM>\n"
        )
        assert extractor.extract(raw) == "Фінальний варіант\n"


class TestCustomTags:
    def test_accepts_custom_open_close(self) -> None:
        ext = SentinelPoemExtractor(open_tag="[[", close_tag="]]")
        raw = "prelude [[Тихо спить]] postlude"
        assert ext.extract(raw) == "Тихо спить\n"

    def test_rejects_empty_tag(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            SentinelPoemExtractor(open_tag="", close_tag="</POEM>")
