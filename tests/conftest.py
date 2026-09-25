from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pandas as pd
import pytest

from core.config import load_settings


RUN_DATE = datetime(2026, 9, 25, tzinfo=timezone.utc)

CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]


def embedding_text(title: str, authors: str, published: str, categories: str, summary: str) -> str:
    return "\n".join(
        [
            f"Title: {title}",
            f"Authors: {authors}",
            f"Published: {published}",
            f"Categories: {categories}",
            f"Summary: {summary}",
        ]
    )


def _row(
    paper_id: str,
    title: str,
    published: str,
    *,
    authors: list[str] | None = None,
    categories: list[str] | None = None,
    summary: str | None = None,
) -> dict:
    author_list = authors if authors is not None else ["Ada Lovelace", "Alan Turing"]
    category_list = categories if categories is not None else ["Artificial Intelligence", "Information Retrieval"]
    summary_text = summary if summary is not None else (
        "This paper studies retrieval augmented generation for scholarly search and cites the source documents."
    )
    authors_joined = ", ".join(author_list)
    categories_joined = ", ".join(category_list)
    published_day = datetime.fromisoformat(published).date()
    return {
        "paper_id": paper_id,
        "title": title,
        "summary": summary_text,
        "authors": author_list,
        "categories": category_list,
        "primary_category": category_list[0] if category_list else "",
        "published": published,
        "updated": published,
        "abs_url": f"https://doi.org/{paper_id}",
        "pdf_url": f"https://doi.org/{paper_id}",
        "comment": f"Crossref record {paper_id}",
        "authors_joined": authors_joined,
        "categories_joined": categories_joined,
        "summary_chars": len(summary_text),
        "age_days": (RUN_DATE.date() - published_day).days,
        "text_for_embedding": embedding_text(title, authors_joined, published, categories_joined, summary_text),
    }


@pytest.fixture
def run_date() -> datetime:
    return RUN_DATE


@pytest.fixture
def clean_df() -> pd.DataFrame:
    """Small dataframe matching the agreed clean schema, newest publication first."""
    rows = [
        _row("10.1000/new", "Newest Paper", "2026-07-01"),
        _row("10.1000/mid-b", "Middle Paper B", "2026-05-01", authors=["Grace Hopper"]),
        _row("10.1000/mid-a", "Middle Paper A", "2026-05-01", categories=["Databases"]),
        _row("10.1000/spring", "Spring Paper", "2026-04-15"),
        _row("10.1000/march", "March Paper", "2026-04-10"),
        _row("10.1000/old", "Old Paper", "2025-01-01", summary="An older study of vector search that still has a long enough abstract."),
    ]
    frame = pd.DataFrame(rows)
    assert list(frame.columns) == CLEAN_COLUMNS
    return frame


@pytest.fixture
def settings(tmp_path):
    base = load_settings()
    data = tmp_path / "data"
    paths = replace(
        base.paths,
        project_dir=tmp_path,
        raw_api_response=data / "raw" / "crossref_response.json",
        raw_records_json=data / "raw" / "crossref_records.json",
        clean_csv=data / "clean" / "papers_clean.csv",
        clean_json=data / "clean" / "papers_clean.json",
        chroma_dir=data / "chroma",
        embeddings_json=data / "embeddings" / "papers_embeddings.json",
        corrupted_embeddings_json=data / "embeddings" / "papers_embeddings_corrupted.json",
        repaired_embeddings_json=data / "embeddings" / "papers_embeddings_repaired.json",
        quality_dir=data / "quality",
        baseline_quality_report=data / "quality" / "baseline_quality_report.json",
        corrupted_quality_report=data / "quality" / "corrupted_quality_report.json",
        freshness_report=data / "quality" / "freshness_report.json",
        eval_testset=data / "eval" / "test_set.json",
        baseline_metrics=data / "results" / "baseline_metrics.json",
        baseline_answers=data / "results" / "baseline_answers.json",
        corruption_log=data / "results" / "corruption_log.json",
    )
    return replace(
        base,
        paths=paths,
        llm_provider="mock",
        refresh_source=False,
        google_api_key=None,
        openai_api_key=None,
        anthropic_api_key=None,
        openrouter_api_key=None,
    )
