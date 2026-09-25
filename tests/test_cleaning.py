"""Tests for ingestion/cleaning.py — dataframe building & text_for_embedding."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion.crossref import PaperRecord
from ingestion.cleaning import build_clean_dataframe


RUN_DATE = datetime(2026, 9, 25, tzinfo=timezone.utc)


def _make_record(**kwargs) -> PaperRecord:
    defaults = dict(
        paper_id="10.1/test",
        title="Test Paper Title",
        summary="This is a sufficiently long summary for testing purposes in this paper.",
        authors=["Alice", "Bob"],
        categories=["cs.AI"],
        primary_category="cs.AI",
        published="2026-06-01",
        updated="2026-06-02",
        abs_url="",
        pdf_url="",
        comment="",
    )
    defaults.update(kwargs)
    return PaperRecord(**defaults)


def test_build_clean_dataframe_columns(clean_df):
    required = {"paper_id", "title", "summary", "text_for_embedding", "age_days", "authors_joined"}
    assert required.issubset(set(clean_df.columns))


def test_text_for_embedding_format(clean_df):
    row = clean_df.iloc[0]
    emb = row["text_for_embedding"]
    assert emb.startswith("Title:")
    assert "Authors:" in emb
    assert "Published:" in emb
    assert "Categories:" in emb
    assert "Summary:" in emb


def test_text_for_embedding_field_order(clean_df):
    row = clean_df.iloc[0]
    emb = row["text_for_embedding"]
    positions = [emb.index(k) for k in ["Title:", "Authors:", "Published:", "Categories:", "Summary:"]]
    assert positions == sorted(positions), "Fields must appear in order: Title/Authors/Published/Categories/Summary"


def test_filters_empty_title():
    bad = _make_record(title="")
    good = _make_record(paper_id="10.1/good")
    df = build_clean_dataframe([bad, good], RUN_DATE)
    assert len(df) == 1
    assert df.iloc[0]["paper_id"] == "10.1/good"


def test_filters_empty_summary():
    bad = _make_record(summary="")
    good = _make_record(paper_id="10.1/good2")
    df = build_clean_dataframe([bad, good], RUN_DATE)
    assert len(df) == 1


def test_dedup_by_paper_id():
    r1 = _make_record(paper_id="10.1/dup")
    r2 = _make_record(paper_id="10.1/dup")
    df = build_clean_dataframe([r1, r2], RUN_DATE)
    assert len(df) == 1


def test_age_days_calculation():
    rec = _make_record(published="2026-03-28")
    df = build_clean_dataframe([rec], RUN_DATE)
    expected = (RUN_DATE.date() - __import__("datetime").date(2026, 3, 28)).days
    assert df.iloc[0]["age_days"] == expected


def test_authors_joined():
    rec = _make_record(authors=["Alice Smith", "Bob Jones"])
    df = build_clean_dataframe([rec], RUN_DATE)
    assert df.iloc[0]["authors_joined"] == "Alice Smith, Bob Jones"


def test_empty_records_returns_empty_df():
    df = build_clean_dataframe([], RUN_DATE)
    assert len(df) == 0
