from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from ingestion.crossref import PaperRecord

_WS_RE = re.compile(r"\s+")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize_ws(text: str) -> str:
    """Normalize whitespace: collapse multiple spaces to single space, strip."""
    return _WS_RE.sub(" ", text).strip()


def _parse_iso_date(value: str | None) -> datetime | None:
    """Parse 'YYYY-MM-DD' string to datetime (date-only), return None if invalid."""
    if not value or not _ISO_RE.match(str(value).strip()):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw PaperRecord list into a deduplicated DataFrame ready for embedding.

    Steps:
    1. Normalise title, summary, authors, categories.
    2. Parse published/updated date.
    3. Calculate age_days = (run_date - published).days.
    4. Create helper columns: authors_joined, categories_joined, summary_chars,
       text_for_embedding.
    5. Drop duplicates by paper_id; drop rows with empty paper_id or title.
    6. Sort by published descending and return.
    """
    rows = []
    for r in records:
        if not r.paper_id or not r.title:
            continue

        published_dt = _parse_iso_date(r.published)

        age_days: int | None = None
        if published_dt is not None:
            age_days = (run_date.date() - published_dt.date()).days

        authors_joined = "; ".join(_normalize_ws(a) for a in r.authors if a)
        categories_joined = "; ".join(_normalize_ws(c) for c in r.categories if c)
        summary_chars = len(r.summary) if r.summary else 0

        text_for_embedding = (
            f"Title: {_normalize_ws(r.title)}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {r.published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {_normalize_ws(r.summary)}"
        )

        rows.append(
            {
                "paper_id": r.paper_id,
                "title": _normalize_ws(r.title),
                "summary": _normalize_ws(r.summary),
                "authors": r.authors,
                "categories": r.categories,
                "primary_category": r.primary_category,
                "published": r.published,
                "updated": r.updated,
                "abs_url": r.abs_url,
                "pdf_url": r.pdf_url,
                "comment": r.comment,
                "published_date": published_dt,
                "age_days": age_days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": summary_chars,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # Deduplicate — keep first occurrence of each paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # Drop rows with missing essential fields
    df = df.dropna(subset=["paper_id", "title"])

    # Sort: newest first
    df = df.sort_values("published_date", ascending=False, na_position="last").reset_index(drop=True)

    return df
