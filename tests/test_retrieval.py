"""Tests for retrieval layer — embeddings, index, qa extraction."""
from __future__ import annotations

import pytest

from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import SearchResult
from retrieval.qa import _extract_answer


def _make_result(authors="Alice", published="2026-01-01", categories="cs.AI", summary="This paper studies graph neural networks.") -> SearchResult:
    return SearchResult(
        paper_id="10.1/test",
        title="Graph Paper",
        score=1.0,
        content=f"Title: Graph Paper\nAuthors: {authors}\nPublished: {published}\nCategories: {categories}\nSummary: {summary}",
        metadata={"authors_joined": authors, "published": published, "categories_joined": categories, "summary": summary},
    )


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def test_miniLM_encode_shape():
    model = MiniLMEmbeddings(MODEL_NAME)
    vecs = model.embed_documents(["Hello world", "Test sentence"])
    assert len(vecs) == 2
    assert len(vecs[0]) == 384  # all-MiniLM-L6-v2 dim


def test_miniLM_encode_single():
    model = MiniLMEmbeddings(MODEL_NAME)
    vecs = model.embed_documents(["Single sentence."])
    assert len(vecs) == 1


def test_miniLM_different_texts_different_vectors():
    model = MiniLMEmbeddings(MODEL_NAME)
    v1 = model.embed_query("Knowledge graphs")
    v2 = model.embed_query("Deep learning transformers")
    assert v1 != v2


def test_extract_answer_summary():
    result = _make_result(summary="This paper studies graph neural networks.")
    ans = _extract_answer("What is 'Graph Paper' about?", result)
    assert ans is not None
    assert "graph" in ans.lower()


def test_extract_answer_authors():
    result = _make_result(authors="Alice Smith, Bob Jones")
    ans = _extract_answer("Who authored 'T'?", result)
    assert ans is not None
    assert "Alice" in ans


def test_extract_answer_date():
    result = _make_result(published="2026-06-15")
    ans = _extract_answer("When was 'T' published?", result)
    assert ans is not None
    assert "2026" in ans


def test_extract_answer_categories():
    result = _make_result(categories="cs.AI, cs.LG")
    ans = _extract_answer("What categories does 'T' belong to?", result)
    assert ans is not None
    assert "cs.AI" in ans


def test_extract_answer_fallback_returns_string():
    result = _make_result()
    ans = _extract_answer("What is the weather today?", result)
    assert isinstance(ans, str)
