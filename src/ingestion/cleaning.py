from __future__ import annotations

from datetime import date, datetime
from html import unescape
import re

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw papers into a stable schema for quality checks and RAG."""
    columns = [
        "paper_id", "title", "summary", "authors", "categories",
        "primary_category", "published", "updated", "age_days",
        "authors_joined", "categories_joined", "summary_chars",
        "text_for_embedding", "abs_url", "pdf_url", "comment",
    ]
    rows = []
    run_day = run_date.date()
    for record in records:
        paper_id = normalize_whitespace(record.paper_id).lower()
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        authors = list(dict.fromkeys(_clean_text(value) for value in record.authors))
        authors = [value for value in authors if value]
        categories = list(dict.fromkeys(_clean_text(value) for value in record.categories))
        categories = [value for value in categories if value]
        try:
            published = date.fromisoformat(record.published[:10])
            updated = date.fromisoformat(record.updated[:10])
        except ValueError:
            continue
        if not paper_id or not title or len(summary) < 30 or not authors or not categories:
            continue

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        text_for_embedding = "\n".join(
            (
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Published: {published.isoformat()}",
                f"Categories: {categories_joined}",
                f"Summary: {summary}",
            )
        )
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": _clean_text(record.primary_category) or categories[0],
                "published": published.isoformat(),
                "updated": updated.isoformat(),
                "age_days": (run_day - published).days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
                "abs_url": normalize_whitespace(record.abs_url),
                "pdf_url": normalize_whitespace(record.pdf_url),
                "comment": normalize_whitespace(record.comment),
            }
        )

    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    df = df.sort_values(["paper_id", "summary_chars"], ascending=[True, False])
    df = df.drop_duplicates(subset="paper_id", keep="first")
    return df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)


def _clean_text(value: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", unescape(str(value))))
