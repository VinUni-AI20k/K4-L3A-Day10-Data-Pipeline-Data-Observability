"""Integration tests for qa.answer_question and metrics.evaluate_pipeline."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def index_and_settings(clean_df, tmp_path):
    from retrieval.index import LocalEmbeddingIndex
    settings = MagicMock()
    settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    settings.top_k = 5
    settings.llm_provider = "mock"
    settings.model_name = "mock"
    settings.paths.chroma_dir = tmp_path / "chroma"
    settings.paths.chroma_dir.mkdir()
    index = LocalEmbeddingIndex.build(clean_df, settings, tmp_path / "emb.json")
    return index, settings


def test_answer_question_summary(index_and_settings, clean_df):
    from retrieval.qa import answer_question
    index, settings = index_and_settings
    title = clean_df.iloc[0]["title"]
    result = answer_question(f"What is '{title}' about?", settings, index)
    assert result.answer is not None
    assert len(result.retrieved_doc_ids) > 0


def test_answer_question_authors(index_and_settings, clean_df):
    from retrieval.qa import answer_question
    index, settings = index_and_settings
    title = clean_df.iloc[0]["title"]
    result = answer_question(f"Who authored '{title}'?", settings, index)
    assert result.answer is not None


def test_answer_question_date(index_and_settings, clean_df):
    from retrieval.qa import answer_question
    index, settings = index_and_settings
    title = clean_df.iloc[1]["title"]
    result = answer_question(f"When was '{title}' published?", settings, index)
    assert "2026" in result.answer


def test_answer_question_categories(index_and_settings, clean_df):
    from retrieval.qa import answer_question
    index, settings = index_and_settings
    title = clean_df.iloc[2]["title"]
    result = answer_question(f"What categories does '{title}' belong to?", settings, index)
    assert result.answer is not None


def test_answer_result_fields(index_and_settings, clean_df):
    from retrieval.qa import answer_question
    index, settings = index_and_settings
    title = clean_df.iloc[0]["title"]
    result = answer_question(f"What is '{title}' about?", settings, index)
    assert hasattr(result, "question")
    assert hasattr(result, "answer")
    assert hasattr(result, "retrieved_doc_ids")
    assert hasattr(result, "retrieved_contexts")


def test_evaluate_pipeline_produces_metrics(index_and_settings, clean_df, tmp_path):
    from evaluation.metrics import evaluate_pipeline
    from evaluation.testset import build_test_set
    index, settings = index_and_settings
    test_set_path = tmp_path / "test_set.json"
    build_test_set(clean_df, test_set_path)
    settings.llm_provider = "mock"
    settings.model_name = "mock"

    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=test_set_path,
        metrics_output_path=tmp_path / "metrics.json",
        answers_output_path=tmp_path / "answers.json",
    )
    assert "retrieval_hit_rate" in bundle.summary
    assert "mean_token_f1" in bundle.summary
    assert 0.0 <= bundle.summary["retrieval_hit_rate"] <= 1.0


def test_crossref_load_raw_records(tmp_path):
    """Test load_raw_records with a local JSON file."""
    import json
    from ingestion.crossref import load_raw_records, PaperRecord
    data = [
        {
            "paper_id": "10.1/x", "title": "T", "summary": "S",
            "authors": ["A"], "categories": ["cs.AI"],
            "primary_category": "cs.AI", "published": "2026-01-01",
            "updated": "2026-01-01", "abs_url": "", "pdf_url": "", "comment": "",
        }
    ]
    path = tmp_path / "records.json"
    path.write_text(json.dumps(data))
    records = load_raw_records(path)
    assert len(records) == 1
    assert isinstance(records[0], PaperRecord)
    assert records[0].paper_id == "10.1/x"
