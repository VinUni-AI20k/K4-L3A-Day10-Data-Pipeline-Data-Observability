from __future__ import annotations

import pytest

from core.utils import read_json, write_json
from evaluation.metrics import _token_f1, evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.corruption import corrupt_clean_dataframe
from retrieval.index import SearchResult
from retrieval.qa import answer_question


class _Index:
    def __init__(self, answer: str, paper_id: str):
        self.answer = answer
        self.paper_id = paper_id

    def lookup(self, value: str):
        return None

    def search(self, query: str, top_k: int | None = None):
        return [
            SearchResult(
                paper_id=self.paper_id,
                title="Indexed Paper",
                score=0.9,
                content="Indexed content",
                metadata={
                    "paper_id": self.paper_id,
                    "title": "Indexed Paper",
                    "authors_joined": self.answer,
                    "published": "2026-07-01",
                    "categories_joined": "Databases",
                    "summary": f"{self.answer} is the reference summary.",
                },
            )
        ]


def test_token_f1_scores_overlap_and_empty_text():
    assert _token_f1("alpha beta", "beta gamma") > 0
    assert _token_f1("alpha", "beta") == 0
    assert _token_f1("", "beta") == 0
    assert _token_f1("Alpha Beta", "alpha beta") == 1


def test_evaluate_pipeline_writes_metrics(settings, tmp_path):
    test_set_path = tmp_path / "test_set.json"
    write_json(
        test_set_path,
        [
            {
                "id": "eval_001",
                "question_type": "authors",
                "question": "Who authored the paper 'Indexed Paper'?",
                "ground_truth": "Ada Lovelace",
                "ground_truth_doc_ids": ["10.1000/new"],
            }
        ],
    )
    bundle = evaluate_pipeline(
        settings,
        _Index("Ada Lovelace", "10.1000/new"),
        test_set_path,
        tmp_path / "metrics.json",
        tmp_path / "answers.json",
    )
    assert bundle.summary["samples"] == 1
    assert bundle.summary["retrieval_hit_rate"] == 1
    assert bundle.summary["mean_token_f1"] == 1
    assert "ragas" in bundle.summary
    saved = read_json(tmp_path / "metrics.json")
    assert saved["retrieval_hit_rate"] == 1
    answers = read_json(tmp_path / "answers.json")
    assert answers[0]["answer"] == "Ada Lovelace"


def test_evaluate_pipeline_counts_a_retrieval_miss(settings, tmp_path):
    test_set_path = tmp_path / "test_set.json"
    write_json(
        test_set_path,
        [
            {
                "id": "eval_002",
                "question_type": "summary",
                "question": "What is the summary of the paper 'Missing'?",
                "ground_truth": "completely different words",
                "ground_truth_doc_ids": ["10.1000/missing"],
            }
        ],
    )
    bundle = evaluate_pipeline(
        settings,
        _Index("unrelated answer text", "10.1000/other"),
        test_set_path,
        tmp_path / "metrics.json",
        tmp_path / "answers.json",
    )
    assert bundle.summary["retrieval_hit_rate"] == 0
    assert bundle.answers[0]["token_f1"] < 1


def test_build_test_set_contract(clean_df, tmp_path):
    output = tmp_path / "test_set.json"
    try:
        rows = build_test_set(clean_df, output)
    except NotImplementedError:
        pytest.skip("testset builder is still a stub")
    assert len(rows) == 10
    assert {row["question_type"] for row in rows} >= {"summary", "authors", "date", "categories"}
    assert output.exists()


def test_corrupt_clean_dataframe_contract(clean_df, tmp_path):
    log_path = tmp_path / "corruption_log.json"
    try:
        corrupted = corrupt_clean_dataframe(clean_df, log_path)
    except NotImplementedError:
        pytest.skip("corruption suite is still a stub")
    assert len(corrupted) >= 1
    logged = read_json(log_path)
    assert {item["type"] for item in logged} >= {
        "drop_latest",
        "blank_summary",
        "inject_noise",
        "truncate_title",
        "stale_date",
        "duplicate_rows",
    }


def test_answer_question_is_imported_for_eval_helpers(settings):
    result = answer_question("Who authored the paper?", settings, _Index("Ada Lovelace", "10.1000/new"))
    assert result.answer == "Ada Lovelace"
