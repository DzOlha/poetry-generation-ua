"""Contract test: FirstLinesStanzaSampler implements IStanzaSampler correctly."""
from __future__ import annotations

from src.domain.ports.detection import IStanzaSampler
from src.infrastructure.detection import FirstLinesStanzaSampler
from src.infrastructure.text import UkrainianTextProcessor
from tests.contracts.stanza_sampler_contract import IStanzaSamplerContract


class TestFirstLinesStanzaSamplerContract(IStanzaSamplerContract):
    def _make_sampler(self) -> IStanzaSampler:
        return FirstLinesStanzaSampler(line_splitter=UkrainianTextProcessor())
