from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a validated tabular DataFrame ready for indexing.

    1. Normalize text fields (title, summary, authors, categories).
    2. Parse dates and calculate `age_days = (run_date - published).days`.
    3. Generate helper columns:
       - `authors_joined`
       - `categories_joined`
       - `summary_chars`
       - `text_for_embedding`
    4. Deduplicate records by unique `paper_id` and filter invalid rows.
    5. Return sorted DataFrame.
    """
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=UTC)
    else:
        run_date = run_date.astimezone(UTC)

    rows: list[dict[str, Any]] = []

    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        if not paper_id:
            continue

        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)

        authors = [normalize_whitespace(a) for a in record.authors if normalize_whitespace(a)]
        authors_joined = compact_join(authors, sep=", ")

        categories = [normalize_whitespace(c) for c in record.categories if normalize_whitespace(c)]
        categories_joined = compact_join(categories, sep=", ")
        primary_category = normalize_whitespace(record.primary_category) or (categories[0] if categories else "General")

        published = record.published.strip()
        try:
            pub_date = datetime.strptime(published[:10], "%Y-%m-%d").replace(tzinfo=UTC)
            age_days = max(0, (run_date - pub_date).days)
        except Exception:
            pub_date = run_date
            age_days = 0

        updated = record.updated.strip() if record.updated else published

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "summary_chars": len(summary),
                "text_for_embedding": text_for_embedding,
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Deduplicate on unique key paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # Filter out empty records
    df = df[df["paper_id"].notna() & (df["paper_id"].str.strip() != "")]
    df = df[df["title"].notna() & (df["title"].str.strip() != "")]

    # Sort deterministically
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
