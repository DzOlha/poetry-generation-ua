from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.retrieval.corpus import CorpusPoem, default_demo_corpus, load_corpus_json
from src.retrieval.retriever import RetrievalItem, SemanticRetriever, build_rag_prompt


class TestCorpusPoem:
    def test_required_fields(self):
        poem = CorpusPoem(id="test_1", text="текст вірша")
        assert poem.id == "test_1"
        assert poem.text == "текст вірша"
        assert poem.author is None
        assert poem.embedding is None

    def test_optional_fields(self):
        poem = CorpusPoem(
            id="test_2",
            text="текст",
            author="Автор",
            approx_theme=["тема"],
            source="src",
            lines=4,
            embedding=[0.1, 0.2],
        )
        assert poem.author == "Автор"
        assert poem.embedding == [0.1, 0.2]


class TestLoadCorpusJson:
    def test_loads_valid_json(self):
        data = [
            {"id": "p1", "text": "вірш один", "author": "А1"},
            {"id": "p2", "text": "вірш два"},
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            path = Path(f.name)

        poems = load_corpus_json(path)
        assert len(poems) == 2
        assert poems[0].id == "p1"
        assert poems[0].author == "А1"
        assert poems[1].author is None
        path.unlink()

    def test_empty_corpus(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([], f)
            f.flush()
            path = Path(f.name)

        poems = load_corpus_json(path)
        assert poems == []
        path.unlink()


class TestDefaultDemoCorpus:
    def test_returns_non_empty_list(self):
        corpus = default_demo_corpus()
        assert len(corpus) >= 2

    def test_each_poem_has_text(self):
        for poem in default_demo_corpus():
            assert poem.text
            assert poem.id


class TestSemanticRetriever:
    def test_encode_returns_list_of_floats(self, retriever: SemanticRetriever):
        vec = retriever.encode("тестова тема")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)
        assert len(vec) > 0

    def test_retrieve_returns_items(self, retriever: SemanticRetriever, demo_corpus: list[CorpusPoem]):
        items = retriever.retrieve("весна у лісі", demo_corpus, top_k=2)
        assert isinstance(items, list)
        assert len(items) <= 2
        for item in items:
            assert isinstance(item, RetrievalItem)
            assert item.poem_id
            assert item.text
            assert isinstance(item.similarity, float)

    def test_retrieve_top_k_limit(self, retriever: SemanticRetriever, demo_corpus: list[CorpusPoem]):
        items = retriever.retrieve("тема", demo_corpus, top_k=1)
        assert len(items) == 1

    def test_retrieve_empty_corpus(self, retriever: SemanticRetriever):
        items = retriever.retrieve("тема", [], top_k=5)
        assert items == []


class TestBuildRagPrompt:
    def test_prompt_contains_components(self):
        retrieved = [
            RetrievalItem(poem_id="p1", text="вірш один", similarity=0.9),
        ]
        prompt = build_rag_prompt(
            theme="весна",
            meter="ямб",
            rhyme_scheme="ABAB",
            retrieved=retrieved,
            stanza_count=2,
            lines_per_stanza=4,
        )
        assert "весна" in prompt
        assert "ямб" in prompt
        assert "ABAB" in prompt
        assert "вірш один" in prompt
        assert "8 lines" in prompt

    def test_prompt_is_string(self):
        prompt = build_rag_prompt("тема", "ямб", "ABAB", [])
        assert isinstance(prompt, str)
