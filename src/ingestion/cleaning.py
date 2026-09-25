from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from html import unescape
import re
from typing import Any

import pandas as pd

from ingestion.crossref import PaperRecord


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_OUTPUT_COLUMNS = [
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


def _clean_text(value: Any, *, strip_markup: bool = False) -> str:
    if value is None:
        return ""
    text = str(value)
    if strip_markup:
        text = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", unescape(text)).strip()


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]

    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = _clean_text(item, strip_markup=True)
        identity = cleaned.casefold()
        if cleaned and identity not in seen:
            result.append(cleaned)
            seen.add(identity)
    return result


def _as_utc_timestamp(value: Any) -> pd.Timestamp | None:
    try:
        timestamp = pd.to_datetime(value, errors="raise", utc=True)
    except (TypeError, ValueError, OverflowError):
        return None
    if pd.isna(timestamp) or not isinstance(timestamp, pd.Timestamp):
        return None
    return timestamp


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw paper records and prepare content for vector indexing.

    Invalid records are removed, duplicate ``paper_id`` values keep their first
    occurrence, and dates are emitted as ISO strings so ChromaDB metadata remains
    serializable. A naive ``run_date`` is interpreted as UTC.
    """
    if not isinstance(run_date, datetime):
        raise TypeError("run_date must be a datetime instance.")

    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize("UTC")
    else:
        run_timestamp = run_timestamp.tz_convert("UTC")

    cleaned_rows: list[dict[str, Any]] = []
    seen_paper_ids: set[str] = set()

    for record in records:
        if not isinstance(record, PaperRecord):
            raise TypeError("records must contain only PaperRecord instances.")

        row = asdict(record)
        paper_id = _clean_text(row["paper_id"])
        title = _clean_text(row["title"], strip_markup=True)
        summary = _clean_text(row["summary"], strip_markup=True)
        identity = paper_id.casefold()
        published_timestamp = _as_utc_timestamp(row["published"])

        if (
            not paper_id
            or not title
            or not summary
            or published_timestamp is None
            or identity in seen_paper_ids
        ):
            continue

        authors = _clean_list(row["authors"])
        categories = _clean_list(row["categories"])
        authors_joined = ", ".join(authors) if authors else "Unknown"
        categories_joined = ", ".join(categories) if categories else "Uncategorized"

        updated_timestamp = _as_utc_timestamp(row["updated"])
        if updated_timestamp is None:
            updated_timestamp = published_timestamp
        published = published_timestamp.date().isoformat()
        updated = updated_timestamp.date().isoformat()
        age_days = int((run_timestamp - published_timestamp).days)

        text_for_embedding = "\n".join(
            [
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Published: {published}",
                f"Categories: {categories_joined}",
                f"Summary: {summary}",
            ]
        )

        cleaned_rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": categories[0] if categories else "Uncategorized",
                "published": published,
                "updated": updated,
                "abs_url": _clean_text(row["abs_url"]),
                "pdf_url": _clean_text(row["pdf_url"]),
                "comment": _clean_text(row["comment"], strip_markup=True),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )
        seen_paper_ids.add(identity)

    if not cleaned_rows:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    dataframe = pd.DataFrame(cleaned_rows, columns=_OUTPUT_COLUMNS)
    dataframe = dataframe.sort_values(
        by=["published", "paper_id"],
        ascending=[False, True],
        kind="stable",
    )
    return dataframe.reset_index(drop=True)
