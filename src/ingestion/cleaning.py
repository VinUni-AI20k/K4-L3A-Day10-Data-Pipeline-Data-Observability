from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.crossref import PaperRecord
from core.utils import compact_join, normalize_whitespace


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a deduplicated embedding-ready dataframe.

    Pseudo-code:
    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    rows = []
    run_ts = pd.Timestamp(run_date)
    if run_ts.tzinfo is None:
        run_ts = run_ts.tz_localize("UTC")
    else:
        run_ts = run_ts.tz_convert("UTC")

    for record in records:
        published = pd.to_datetime(record.published, utc=True, errors="coerce")
        if pd.isna(published):
            continue
        updated = pd.to_datetime(record.updated, utc=True, errors="coerce")
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        authors = [normalize_whitespace(value) for value in record.authors if normalize_whitespace(value)]
        categories = [normalize_whitespace(value) for value in record.categories if normalize_whitespace(value)]
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        published_date = published.date().isoformat()
        text = (
            f"Title: {title}\nAuthors: {authors_joined}\nPublished: {published_date}\n"
            f"Categories: {categories_joined}\nSummary: {summary}"
        )
        rows.append(
            {
                "paper_id": normalize_whitespace(record.paper_id).lower(),
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category),
                "published": published_date,
                "updated": updated.date().isoformat() if not pd.isna(updated) else published_date,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
                "age_days": max(0, int((run_ts - published).days)),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": text,
            }
        )
    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "abs_url", "pdf_url", "comment", "age_days",
        "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]

    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    df = df[df["paper_id"].ne("") & df["title"].ne("")]
    return df.drop_duplicates(subset=["paper_id"], keep="first").sort_values(
        ["published", "paper_id"], ascending=[False, True]
    ).reset_index(drop=True)
