from __future__ import annotations

import re
from datetime import datetime, timezone

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = _TAG_RE.sub(" ", str(value))
    return normalize_whitespace(without_tags)


def _clean_items(items: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for item in items or []:
        text = _clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt, width in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
            try:
                parsed = datetime.strptime(normalized[:width], fmt)
                break
            except ValueError:
                parsed = None
    if parsed is None:
        return None
    return _to_utc(parsed)


def _format_date(value: datetime) -> str:
    return value.date().isoformat()


def _embedding_text(
    title: str,
    authors_joined: str,
    published: str,
    categories_joined: str,
    summary: str,
) -> str:
    return (
        f"Title: {title}\n"
        f"Authors: {authors_joined}\n"
        f"Published: {published}\n"
        f"Categories: {categories_joined}\n"
        f"Summary: {summary}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a dataframe ready for embedding.

    Normalizes text, computes age_days, builds text_for_embedding,
    drops duplicate paper_id values, and filters unusable rows.
    """
    run_utc = _to_utc(run_date)
    rows: list[dict] = []

    for record in records:
        paper_id = _clean_text(record.paper_id)
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        authors = _clean_items(record.authors)
        categories = _clean_items(record.categories)
        published_dt = _parse_datetime(record.published)
        if not paper_id or not title or published_dt is None:
            continue

        updated_dt = _parse_datetime(record.updated)
        published = _format_date(published_dt)
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        primary_category = _clean_text(record.primary_category) or (categories[0] if categories else "")

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": _format_date(updated_dt) if updated_dt else published,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
                "age_days": (run_utc - published_dt).days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": _embedding_text(
                    title,
                    authors_joined,
                    published,
                    categories_joined,
                    summary,
                ),
            }
        )

    columns = [
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
        "age_days",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "text_for_embedding",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame

    frame = frame.drop_duplicates(subset=["paper_id"], keep="first")
    frame = frame.sort_values(["published", "paper_id"], ascending=[False, True])
    return frame.reset_index(drop=True)
