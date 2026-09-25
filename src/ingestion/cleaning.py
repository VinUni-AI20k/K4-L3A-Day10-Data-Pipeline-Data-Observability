from __future__ import annotations

from datetime import UTC, datetime
import html
import re
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    return normalize_whitespace(text)


def _clean_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean_text(value)
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def _parse_date(value: Any) -> pd.Timestamp | pd.NaT:
    if value is None:
        return pd.NaT
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return pd.NaT
    return parsed.normalize()


def _age_days(published: pd.Timestamp, run_date: datetime) -> int | None:
    if pd.isna(published):
        return None
    run_ts = pd.Timestamp(run_date)
    if run_ts.tzinfo is None:
        run_ts = run_ts.tz_localize(UTC)
    else:
        run_ts = run_ts.tz_convert(UTC)
    return max(0, int((run_ts.normalize() - published).days))


def _embedding_text(row: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw Crossref records into a deterministic dataframe for embedding."""
    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = _clean_text(record.paper_id).lower()
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        primary_category = _clean_text(record.primary_category) or (categories[0] if categories else "")
        published_ts = _parse_date(record.published)
        updated_ts = _parse_date(record.updated)

        published = published_ts.date().isoformat() if not pd.isna(published_ts) else ""
        updated = updated_ts.date().isoformat() if not pd.isna(updated_ts) else ""
        row = {
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": primary_category,
            "published": published,
            "updated": updated,
            "abs_url": _clean_text(record.abs_url),
            "pdf_url": _clean_text(record.pdf_url),
            "comment": _clean_text(record.comment),
            "authors_joined": compact_join(authors),
            "categories_joined": compact_join(categories),
            "summary_chars": len(summary),
            "age_days": _age_days(published_ts, run_date),
        }
        row["text_for_embedding"] = _embedding_text(row)
        rows.append(row)

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
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    df = df.dropna(subset=["paper_id", "title", "summary"])
    df = df[
        (df["paper_id"].astype(str).str.len() > 0)
        & (df["title"].astype(str).str.len() > 0)
        & (df["summary"].astype(str).str.len() >= 30)
        & (df["published"].astype(str).str.len() > 0)
    ].copy()
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
