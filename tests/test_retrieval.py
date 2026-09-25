from __future__ import annotations

from dataclasses import replace

import pytest

from core.config import load_settings, normalized_provider, require_llm_credentials
from core.utils import now_utc, write_csv, write_text
from retrieval.agent import build_agent, run_agent_question
from retrieval.embeddings import MiniLMEmbeddings
from retrieval.index import LocalEmbeddingIndex, SearchResult
from retrieval.llm import build_llm
from retrieval.qa import answer_question


class _FakeEmbeddings:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), 0.2, 0.3] for index, _text in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.2, 0.3]


class _Corpus:
    def __init__(self):
        self.metadata = {
            "paper_id": "10.1000/new",
            "title": "Newest Paper",
            "authors_joined": "Ada Lovelace, Alan Turing",
            "published": "2026-07-01",
            "categories_joined": "Artificial Intelligence, Information Retrieval",
            "summary": "First sentence about retrieval. Second sentence.",
        }

    def lookup(self, value: str):
        if value == "Newest Paper":
            return {
                "paper_id": self.metadata["paper_id"],
                "title": self.metadata["title"],
                "content": "Title: Newest Paper",
                "metadata": self.metadata,
            }
        return None

    def search(self, query: str, top_k: int | None = None):
        if "unknown" in query.lower():
            return []
        return [
            SearchResult(
                paper_id="10.1000/other",
                title="Other Paper",
                score=0.2,
                content="other",
                metadata={
                    "paper_id": "10.1000/other",
                    "title": "Other Paper",
                    "authors_joined": "Grace Hopper",
                    "published": "2026-01-01",
                    "categories_joined": "Databases",
                    "summary": "Other summary sentence.",
                },
            )
        ]


def test_answer_question_uses_exact_title_and_question_type(settings):
    corpus = _Corpus()
    authored = answer_question("Who authored the paper 'Newest Paper'?", settings, corpus)
    assert authored.answer == "Ada Lovelace, Alan Turing"
    assert authored.retrieved_doc_ids[0] == "10.1000/new"

    dated = answer_question("When was the paper 'Newest Paper' published?", settings, corpus)
    assert dated.answer == "2026-07-01"
    listed = answer_question("List the authors of 'Newest Paper'", settings, corpus)
    assert listed.answer == "Ada Lovelace, Alan Turing"
    published_on = answer_question("Which publication date is on 'Newest Paper'?", settings, corpus)
    assert published_on.answer == "2026-07-01"
    categories = answer_question("What categories does the paper 'Newest Paper' belong to?", settings, corpus)
    assert "Artificial Intelligence" in categories.answer
    summary = answer_question("What is the summary of the paper 'Newest Paper'?", settings, corpus)
    assert summary.answer == "First sentence about retrieval."
    unknown = answer_question("Tell me about an unknown topic", settings, corpus)
    assert unknown.answer == "I don't know from the indexed corpus."


def test_local_index_builds_searches_and_reloads(settings, clean_df, monkeypatch):
    monkeypatch.setattr("retrieval.index.MiniLMEmbeddings", _FakeEmbeddings)
    LocalEmbeddingIndex.build(clean_df, settings)
    again = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    assert again.collection_name == settings.baseline_collection_name
    assert again.lookup(clean_df.iloc[0]["title"])["paper_id"] == clean_df.iloc[0]["paper_id"]
    assert again.lookup("missing-paper") is None
    assert again.search("Newest Paper", top_k=2)

    corrupted = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.corrupted_embeddings_json)
    repaired = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.repaired_embeddings_json)
    custom = LocalEmbeddingIndex.build(clean_df.iloc[:1], settings, settings.paths.project_dir / "custom_vectors.json")
    assert corrupted.collection_name == settings.corrupted_collection_name
    assert repaired.collection_name == settings.repaired_collection_name
    assert custom.collection_name == "custom-vectors"

    class _Query:
        def query(self, **_kwargs):
            return {
                "ids": [["", "kept"]],
                "documents": [["", "kept document"]],
                "metadatas": [[None, {"paper_id": "10.1000/new", "title": "Newest Paper"}]],
                "distances": [[0.1, 1.5]],
            }

    again.collection = _Query()
    hits = again.search("query", top_k=2)
    assert len(hits) == 1
    assert hits[0].paper_id == "10.1000/new"
    assert hits[0].score == 0

    loaded = LocalEmbeddingIndex.load(settings, settings.paths.embeddings_json)
    assert loaded.collection_name == settings.baseline_collection_name


def test_embeddings_delegate_to_the_sentence_transformer(monkeypatch):
    class _Model:
        def encode(self, texts, normalize_embeddings=True):
            import numpy as np

            return np.array([[0.25, 0.75] for _text in texts])

    monkeypatch.setattr("retrieval.embeddings._load_model", lambda _name: _Model())
    embedder = MiniLMEmbeddings("unit-test-model")
    assert embedder.embed_query("hello") == [0.25, 0.75]
    assert embedder.embed_documents(["a", "b"]) == [[0.25, 0.75], [0.25, 0.75]]


def test_provider_names_and_credentials():
    base = load_settings()
    assert normalized_provider(replace(base, llm_provider=" anthorpic ")) == "anthropic"
    assert normalized_provider(replace(base, llm_provider="Custom-LLM")) == "custom"
    mock_settings = replace(base, llm_provider="mock")
    require_llm_credentials(mock_settings)
    require_llm_credentials(replace(base, llm_provider="ollama"))

    for provider, field in (
        ("gemini", "google_api_key"),
        ("openai", "openai_api_key"),
        ("anthropic", "anthropic_api_key"),
        ("openrouter", "openrouter_api_key"),
    ):
        with pytest.raises(RuntimeError):
            require_llm_credentials(replace(base, llm_provider=provider, **{field: None}))
        require_llm_credentials(replace(base, llm_provider=provider, **{field: "test-key"}))

    with pytest.raises(RuntimeError):
        require_llm_credentials(replace(base, llm_provider="custom", custom_llm_base_url=None))
    require_llm_credentials(replace(base, llm_provider="custom", custom_llm_base_url="http://localhost:9"))
    with pytest.raises(RuntimeError):
        require_llm_credentials(replace(base, llm_provider="no-such-provider"))


def test_build_llm_for_each_supported_provider():
    base = replace(
        load_settings(),
        google_api_key="test-key",
        openai_api_key="test-key",
        anthropic_api_key="test-key",
        openrouter_api_key="test-key",
        custom_llm_api_key="test-key",
        custom_llm_base_url="http://localhost:9/v1",
    )
    mock_llm = build_llm(replace(base, llm_provider="mock"))
    assert mock_llm.invoke("hi").content
    for provider in ("gemini", "openai", "anthropic", "openrouter", "ollama", "custom"):
        model = build_llm(replace(base, llm_provider=provider))
        assert model is not None
    with pytest.raises(RuntimeError):
        build_llm(replace(base, llm_provider="no-such-provider"))


def test_agent_tools_search_and_lookup(settings, clean_df, monkeypatch):
    monkeypatch.setattr("retrieval.index.MiniLMEmbeddings", _FakeEmbeddings)
    captured: dict = {}

    def _capture_agent(**kwargs):
        captured["tools"] = kwargs["tools"]

        class _Built:
            pass

        return _Built()

    monkeypatch.setattr("retrieval.agent.create_agent", _capture_agent)
    index = LocalEmbeddingIndex.build(clean_df.iloc[:2], settings, settings.paths.project_dir / "agent_vectors.json")
    build_agent(settings, index)
    tools = {tool.name: tool for tool in captured["tools"]}
    found = tools["lookup_paper"].invoke({"paper_id_or_title": clean_df.iloc[0]["title"]})
    assert clean_df.iloc[0]["paper_id"] in found
    missing = tools["lookup_paper"].invoke({"paper_id_or_title": "not-in-the-index"})
    assert "No exact paper match" in missing
    searched = tools["semantic_search_papers"].invoke({"query": "retrieval", "top_k": 1})
    assert "paper_id:" in searched

    class _Message:
        content = "mock answer"

    class _Agent:
        def invoke(self, _payload):
            return {"messages": [_Message()]}

    assert run_agent_question(_Agent(), "question") == "mock answer"

    class _EmptyAgent:
        def invoke(self, _payload):
            return {"messages": []}

    assert run_agent_question(_EmptyAgent(), "question") == ""

    class _PlainAgent:
        def invoke(self, _payload):
            return {"messages": ["plain text"]}

    assert run_agent_question(_PlainAgent(), "question") == "plain text"


def test_core_io_helpers(tmp_path):
    frame_path = tmp_path / "nested" / "rows.csv"
    text_path = tmp_path / "nested" / "note.txt"
    import pandas as pd

    write_csv(pd.DataFrame({"paper_id": ["10.1000/a"]}), frame_path)
    write_text(text_path, "ok")
    assert frame_path.exists()
    assert text_path.read_text(encoding="utf-8") == "ok"
    assert now_utc().tzinfo is not None
