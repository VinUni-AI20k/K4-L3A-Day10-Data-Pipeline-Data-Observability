"""Shared fixtures for all tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion.crossref import PaperRecord


@pytest.fixture
def sample_records() -> list[PaperRecord]:
    return [
        PaperRecord(
            paper_id=f"10.1000/test.{i:03d}",
            title=f"Sample Paper {i}: A Study on Knowledge Graphs",
            summary="This paper presents a comprehensive study on knowledge graph embeddings and their applications in information retrieval systems.",
            authors=[f"Author A{i}", f"Author B{i}"],
            categories=["cs.AI", "cs.IR"],
            primary_category="cs.AI",
            published="2026-01-15",
            updated="2026-01-20",
            abs_url=f"https://example.com/abs/{i}",
            pdf_url=f"https://example.com/pdf/{i}",
            comment="",
        )
        for i in range(1, 11)
    ]


@pytest.fixture
def run_date() -> datetime:
    return datetime(2026, 9, 25, tzinfo=timezone.utc)


@pytest.fixture
def clean_df(sample_records, run_date):
    from ingestion.cleaning import build_clean_dataframe
    return build_clean_dataframe(sample_records, run_date)
