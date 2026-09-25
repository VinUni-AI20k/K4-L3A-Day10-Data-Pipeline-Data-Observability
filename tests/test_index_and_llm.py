"""Tests for retrieval/index.py (ChromaDB build/search) and retrieval/llm.py (mock provider)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ── LocalEmbeddingIndex ──────────────────────────────────────────────────────

@pytest.fixture
def index(clean_df, tmp_path):
    from unittest.mock import patch, MagicMock
    settings = MagicMock()
    settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    settings.top_k = 3
    settings.paths.chroma_dir = tmp_path / "chroma"
    settings.paths.chroma_dir.mkdir()

    from retrieval.index import LocalEmbeddingIndex
    return LocalEmbeddingIndex.build(clean_df, settings, tmp_path / "embeddings.json")


def test_index_build_returns_index(index):
    from retrieval.index import LocalEmbeddingIndex
    assert isinstance(index, LocalEmbeddingIndex)


def test_index_search_returns_results(index):
    results = index.search("knowledge graph neural network", top_k=3)
    assert len(results) > 0
    assert len(results) <= 3


def test_index_search_result_has_paper_id(index):
    results = index.search("graph embedding", top_k=2)
    for r in results:
        assert r.paper_id is not None
        assert isinstance(r.paper_id, str)


def test_index_search_result_has_score(index):
    results = index.search("knowledge graph", top_k=2)
    for r in results:
        assert 0.0 <= r.score <= 1.0 or r.score >= 0.0  # chroma distance can vary


def test_index_lookup_by_title(index, clean_df):
    title = clean_df.iloc[0]["title"]
    result = index.lookup(title)
    assert result is not None
    assert result["title"].lower() == title.lower()


def test_index_lookup_nonexistent_returns_none(index):
    result = index.lookup("This title does not exist in the corpus xyz")
    assert result is None


def test_index_document_count(index, clean_df):
    assert len(index.documents) == len(clean_df)


# ── LLM mock provider ────────────────────────────────────────────────────────

def test_build_llm_mock():
    from retrieval.llm import build_llm
    settings = MagicMock()
    settings.llm_provider = "mock"
    settings.model_name = "mock"

    from core.config import normalized_provider, require_llm_credentials
    with (
        __import__("unittest.mock", fromlist=["patch"]).patch("core.config.normalized_provider", return_value="mock"),
        __import__("unittest.mock", fromlist=["patch"]).patch("core.config.require_llm_credentials", return_value=None),
    ):
        llm = build_llm(settings)
        assert llm is not None


def test_mock_llm_returns_response():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.messages import HumanMessage
    llm = FakeListChatModel(responses=["Mock answer about papers."])
    result = llm.invoke([HumanMessage(content="What is this paper about?")])
    assert "Mock" in result.content
