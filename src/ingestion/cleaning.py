from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw paper records into a dataframe ready for quality checks and embeddings."""
    normalized_run_date = _as_utc(run_date)
    rows: list[dict] = []

    for record in records:
        paper_id = normalize_whitespace(record.paper_id).lower()
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        authors = [_clean_item(author) for author in record.authors]
        categories = [_clean_item(category) for category in record.categories]
        authors = [author for author in authors if author]
        categories = [category for category in categories if category]

        if not paper_id or not title or not summary:
            continue

        published_dt = _parse_date(record.published)
        updated_dt = _parse_date(record.updated) if record.updated else published_dt
        age_days = max(0, (normalized_run_date.date() - published_dt.date()).days)
        authors_joined = compact_join(authors) or "Unknown"
        categories_joined = compact_join(categories) or "Uncategorized"

        row = {
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": categories[0] if categories else "Uncategorized",
            "published": published_dt.date().isoformat(),
            "updated": updated_dt.date().isoformat(),
            "age_days": age_days,
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "abs_url": normalize_whitespace(record.abs_url),
            "pdf_url": normalize_whitespace(record.pdf_url),
            "comment": normalize_whitespace(record.comment),
        }
        row["text_for_embedding"] = (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        )
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df[df["summary_chars"] >= 30]
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df


def _clean_item(value: str) -> str:
    return normalize_whitespace(str(value))


def _parse_date(value: str) -> datetime:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return datetime.now(UTC)
    return parsed.to_pydatetime()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
