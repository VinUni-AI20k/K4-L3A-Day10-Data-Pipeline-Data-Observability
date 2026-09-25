"""Tests for evaluation — testset generation & token_f1 metric."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.testset import build_test_set
from evaluation.metrics import _token_f1


# ── testset ─────────────────────────────────────────────────────────────────

def test_build_test_set_count(clean_df, tmp_path):
    out = tmp_path / "test_set.json"
    items = build_test_set(clean_df, out)
    assert len(items) == 10


def test_build_test_set_question_types(clean_df, tmp_path):
    out = tmp_path / "test_set.json"
    items = build_test_set(clean_df, out)
    types = [i["question_type"] for i in items]
    assert types.count("summary") == 3
    assert types.count("authors") == 3
    assert types.count("date") == 2
    assert types.count("categories") == 2


def test_build_test_set_has_required_fields(clean_df, tmp_path):
    out = tmp_path / "test_set.json"
    items = build_test_set(clean_df, out)
    for item in items:
        assert "id" in item
        assert "question" in item
        assert "ground_truth" in item
        assert "ground_truth_doc_ids" in item


def test_build_test_set_saves_json(clean_df, tmp_path):
    out = tmp_path / "test_set.json"
    build_test_set(clean_df, out)
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert len(loaded) == 10


def test_build_test_set_returns_cached(clean_df, tmp_path):
    out = tmp_path / "test_set.json"
    first = build_test_set(clean_df, out)
    second = build_test_set(clean_df, out)  # should load from file
    assert first == second


def test_build_test_set_raises_on_too_few_docs(clean_df, tmp_path):
    out = tmp_path / "test_set.json"
    with pytest.raises(ValueError, match="at least 4"):
        build_test_set(clean_df.iloc[:2], out)


def test_summary_question_format(clean_df, tmp_path):
    items = build_test_set(clean_df, tmp_path / "ts.json")
    summary_qs = [i for i in items if i["question_type"] == "summary"]
    for q in summary_qs:
        assert "about?" in q["question"]


def test_authors_question_format(clean_df, tmp_path):
    items = build_test_set(clean_df, tmp_path / "ts.json")
    author_qs = [i for i in items if i["question_type"] == "authors"]
    for q in author_qs:
        assert "authored" in q["question"]


# ── token_f1 ─────────────────────────────────────────────────────────────────

def test_token_f1_perfect_match():
    assert _token_f1("hello world", "hello world") == pytest.approx(1.0)


def test_token_f1_no_overlap():
    assert _token_f1("hello world", "foo bar") == pytest.approx(0.0)


def test_token_f1_partial_overlap():
    score = _token_f1("hello world test", "hello foo")
    assert 0.0 < score < 1.0


def test_token_f1_empty_prediction():
    assert _token_f1("hello world", "") == pytest.approx(0.0)


def test_token_f1_empty_reference():
    assert _token_f1("", "hello world") == pytest.approx(0.0)


def test_token_f1_case_insensitive():
    assert _token_f1("Hello World", "hello world") == pytest.approx(1.0)
