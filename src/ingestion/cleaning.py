from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw paper records into the vector-index data contract."""
    columns = [
        "paper_id",
        "title",
        "summary",
        "authors",
        "categories",
        "primary_category",
        "published",
        "updated",
        "age_days",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "text_for_embedding",
        "abs_url",
        "pdf_url",
        "comment",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    def clean_list(values: Any) -> list[str]:
        if not isinstance(values, (list, tuple, set)):
            values = [values] if values else []
        return list(
            dict.fromkeys(
                item
                for item in (normalize_whitespace(str(value or "")) for value in values)
                if item
            )
        )

    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=UTC)
    else:
        run_date = run_date.astimezone(UTC)

    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = normalize_whitespace(record.paper_id).lower()
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        authors = clean_list(record.authors)
        categories = clean_list(record.categories)
        published = pd.to_datetime(record.published, utc=True, errors="coerce")
        updated = pd.to_datetime(record.updated, utc=True, errors="coerce")

        # Invalid source rows are excluded before indexing; corruption is injected
        # later so that the observability gate can demonstrate detection.
        if not paper_id or not title or len(summary) < 30 or pd.isna(published):
            continue
        if pd.isna(updated):
            updated = published

        authors_joined = ", ".join(authors) if authors else "Unknown"
        categories_joined = ", ".join(categories) if categories else "Uncategorized"
        published_text = published.date().isoformat()
        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category)
                or categories_joined.split(",", 1)[0],
                "published": published_text,
                "updated": updated.date().isoformat(),
                "age_days": (run_date.date() - published.date()).days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": "\n".join(
                    [
                        f"Title: {title}",
                        f"Authors: {authors_joined}",
                        f"Published: {published_text}",
                        f"Categories: {categories_joined}",
                        f"Summary: {summary}",
                    ]
                ),
                "abs_url": normalize_whitespace(record.abs_url),
                "pdf_url": normalize_whitespace(record.pdf_url),
                "comment": normalize_whitespace(record.comment),
            }
        )

    cleaned = pd.DataFrame(rows, columns=columns)
    if cleaned.empty:
        return cleaned
    cleaned = cleaned.drop_duplicates(subset=["paper_id"], keep="first")
    return cleaned.sort_values(
        by=["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
