"""Unit tests for FirstLinesStanzaSampler."""
from __future__ import annotations

from src.infrastructure.detection import FirstLinesStanzaSampler
from src.infrastructure.text import UkrainianTextProcessor


def _make_sampler() -> FirstLinesStanzaSampler:
    return FirstLinesStanzaSampler(line_splitter=UkrainianTextProcessor())


class TestFirstLinesStanzaSampler:
    def test_sample_4_lines(self) -> None:
        text = "Рядок один\nРядок два\nРядок три\nРядок чотири\nРядок п'ять"
        result = _make_sampler().sample(text, 4)
        assert result is not None
        assert len(result.splitlines()) == 4

    def test_sample_returns_none_if_too_short(self) -> None:
        text = "Рядок один\nРядок два"
        result = _make_sampler().sample(text, 4)
        assert result is None

    def test_sample_2_lines(self) -> None:
        text = "Рядок один\nРядок два\nРядок три"
        result = _make_sampler().sample(text, 2)
        assert result is not None
        assert len(result.splitlines()) == 2

    def test_sample_14_lines_for_sonnet(self) -> None:
        lines = [f"Рядок {i}" for i in range(1, 16)]
        text = "\n".join(lines)
        result = _make_sampler().sample(text, 14)
        assert result is not None
        assert len(result.splitlines()) == 14

    def test_skips_blank_lines(self) -> None:
        text = "Рядок один\n\n\nРядок два\n\nРядок три\nРядок чотири"
        result = _make_sampler().sample(text, 4)
        assert result is not None
        assert len(result.splitlines()) == 4

    def test_exact_line_count(self) -> None:
        text = "Рядок один\nРядок два\nРядок три\nРядок чотири"
        result = _make_sampler().sample(text, 4)
        assert result is not None
        assert len(result.splitlines()) == 4
