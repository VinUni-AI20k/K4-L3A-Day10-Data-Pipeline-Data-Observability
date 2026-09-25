from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from ingestion.crossref import PaperRecord


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _as_iso_date(value: object) -> str:
    if value in (None, ""):
        return ""
    dt = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(dt):
        return ""
    return dt.strftime("%Y-%m-%d")


def _naive_utc(ts: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a dataframe ready for embedding.

    The function normalizes text fields, parses dates, calculates freshness metrics,
    builds helper columns used downstream, removes invalid/duplicate records, then
    returns a sorted dataframe ready for indexing.
    """
    run_ts = _naive_utc(pd.Timestamp(run_date))
    rows: list[dict] = []

    for record in records:
        paper_id = _normalize_text(record.paper_id)
        title = _normalize_text(record.title)
        summary = _normalize_text(record.summary)

        if not paper_id or not title or not summary:
            continue

        authors = [_normalize_text(author) for author in (record.authors or [])]
        authors = [author for author in authors if author]
        categories = [_normalize_text(category) for category in (record.categories or [])]
        categories = [category for category in categories if category]

        published = _as_iso_date(record.published)
        updated = _as_iso_date(record.updated) or published
        published_dt = pd.to_datetime(published, errors="coerce", utc=True)

        if pd.isna(published_dt):
            continue

        age_days = int((run_ts - _naive_utc(published_dt)).days)

        row = {
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": _normalize_text(record.primary_category) or (categories[0] if categories else "Uncategorized"),
            "published": published,
            "updated": updated,
            "abs_url": _normalize_text(record.abs_url),
            "pdf_url": _normalize_text(record.pdf_url),
            "comment": _normalize_text(record.comment),
            "authors_joined": "; ".join(authors),
            "categories_joined": "; ".join(categories),
            "summary_chars": len(summary),
            "age_days": age_days,
        }
        row["text_for_embedding"] = (
            "Title: "
            f"{row['title']}\n"
            "Authors: "
            f"{row['authors_joined']}\n"
            "Published: "
            f"{row['published']}\n"
            "Categories: "
            f"{row['categories_joined']}\n"
            "Summary: "
            f"{row['summary']}"
        )
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.drop_duplicates(subset=["paper_id"], keep="first").copy()
    df = df[df["title"].str.len() > 0].copy()
    df = df[df["summary"].str.len() >= 20].copy()
    df = df.sort_values(["published", "paper_id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    return df
