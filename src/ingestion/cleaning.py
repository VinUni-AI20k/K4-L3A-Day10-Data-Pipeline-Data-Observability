from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord

def build_clean_dataframe(
    records: list[PaperRecord],
    run_date: datetime,
) -> pd.DataFrame:

    rows = []

    run_timestamp = pd.Timestamp(run_date)

    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize("UTC")

    for record in records:
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)

        authors = [
            normalize_whitespace(author)
            for author in record.authors
            if normalize_whitespace(author)
        ]

        categories = [
            normalize_whitespace(category)
            for category in record.categories
            if normalize_whitespace(category)
        ]

        if not record.paper_id or not title:
            continue

        published_ts = pd.to_datetime(
            record.published,
            utc=True,
            errors="coerce",
        )

        updated_ts = pd.to_datetime(
            record.updated,
            utc=True,
            errors="coerce",
        )

        if pd.isna(published_ts):
            continue

        age_days = max(
            0,
            int((run_timestamp - published_ts).days),
        )

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)

        published = published_ts.strftime("%Y-%m-%d")

        updated = (
            updated_ts.isoformat()
            if not pd.isna(updated_ts)
            else ""
        )

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
         )

        rows.append(
            {
                "paper_id": record.paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": record.primary_category,
                "published": published,
                "updated": updated,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
                "age_days": age_days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = (
        df.drop_duplicates(
            subset=["paper_id"],
            keep="last",
        )
        .sort_values(
            by=["published", "paper_id"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    return df
