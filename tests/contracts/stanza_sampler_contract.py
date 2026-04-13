"""Behavioural contract for IStanzaSampler implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.ports.detection import IStanzaSampler


class IStanzaSamplerContract(ABC):
    """Shared behavioural expectations for any IStanzaSampler implementation."""

    @abstractmethod
    def _make_sampler(self) -> IStanzaSampler: ...

    def test_returns_exact_line_count(self) -> None:
        sampler = self._make_sampler()
        text = "A\nB\nC\nD\nE"
        result = sampler.sample(text, 4)
        assert result is not None
        assert len(result.splitlines()) == 4

    def test_returns_none_when_too_few_lines(self) -> None:
        sampler = self._make_sampler()
        result = sampler.sample("A\nB", 4)
        assert result is None

    def test_two_line_sample(self) -> None:
        sampler = self._make_sampler()
        result = sampler.sample("A\nB\nC", 2)
        assert result is not None
        assert len(result.splitlines()) == 2
