from __future__ import annotations

from datetime import date, datetime
import html
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize records, compute age_days, and build embedding text."""
    run_day = _as_date(run_date)
    rows: list[dict] = []
    for record in records:
        title = normalize_whitespace(record.title)
        summary = _strip_markup(record.summary)
        authors = [normalize_whitespace(author) for author in record.authors if normalize_whitespace(author)]
        categories = [
            normalize_whitespace(category)
            for category in record.categories
            if normalize_whitespace(category)
        ]
        published = _as_date(record.published)
        if not record.paper_id or not title or published is None:
            continue

        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        published_iso = published.isoformat()
        row = {
            "paper_id": record.paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": normalize_whitespace(record.primary_category) or (categories[0] if categories else ""),
            "published": published_iso,
            "updated": _iso_or_blank(record.updated) or published_iso,
            "abs_url": normalize_whitespace(record.abs_url),
            "pdf_url": normalize_whitespace(record.pdf_url),
            "comment": normalize_whitespace(record.comment),
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "age_days": (run_day - published).days,
        }
        row["text_for_embedding"] = compose_text_for_embedding(row)
        rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.drop_duplicates(subset=["paper_id"], keep="first")
    frame = frame.sort_values(by=["published", "paper_id"], ascending=[False, True], kind="stable").reset_index(drop=True)
    return frame


def compose_text_for_embedding(row: dict) -> str:
    """Build the five-line embedding document shared with later pipeline stages."""
    return "\n".join(
        [
            f"Title: {row.get('title') or ''}",
            f"Authors: {row.get('authors_joined') or ''}",
            f"Published: {row.get('published') or ''}",
            f"Categories: {row.get('categories_joined') or ''}",
            f"Summary: {row.get('summary') or ''}",
        ]
    )


def _strip_markup(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(text)


def _as_date(value: datetime | date | str | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_whitespace(str(value or ""))
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _iso_or_blank(value: str) -> str:
    parsed = _as_date(value)
    return parsed.isoformat() if parsed else ""
