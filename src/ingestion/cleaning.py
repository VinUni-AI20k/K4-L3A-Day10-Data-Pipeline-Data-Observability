from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def _calculate_age_days(published_val: Any, run_date: datetime) -> int:
    if run_date.tzinfo is not None:
        run_date_utc = run_date.astimezone(timezone.utc)
    else:
        run_date_utc = run_date.replace(tzinfo=timezone.utc)

    if isinstance(published_val, (datetime, pd.Timestamp)):
        pub_dt = published_val
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        else:
            pub_dt = pub_dt.astimezone(timezone.utc)
    else:
        try:
            pub_dt = pd.to_datetime(str(published_val), utc=True)
        except Exception:
            return 0
    return max(0, (run_date_utc - pub_dt).days)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days = (run_date - published).days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates theo paper_id va filter row xau.
    6. Sort dataframe va return.
    """
    rows: list[dict[str, Any]] = []

    for record in records:
        if isinstance(record, PaperRecord):
            data = asdict(record)
        elif isinstance(record, dict):
            data = dict(record)
        else:
            continue

        paper_id = str(data.get("paper_id", "")).strip()
        if not paper_id:
            continue

        title = normalize_whitespace(str(data.get("title", "")))
        summary = normalize_whitespace(str(data.get("summary", "")))

        authors = data.get("authors", [])
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        authors_joined = compact_join(authors, sep=", ")

        categories = data.get("categories", [])
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(",") if c.strip()]
        categories_joined = compact_join(categories, sep=", ")

        primary_category = str(data.get("primary_category", "")).strip()
        if not primary_category and categories:
            primary_category = categories[0]

        published = str(data.get("published", "")).strip()
        updated = str(data.get("updated", "")).strip() or published

        age_days = _calculate_age_days(published, run_date)
        summary_chars = len(summary)

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
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "abs_url": str(data.get("abs_url", "")),
                "pdf_url": str(data.get("pdf_url", "")),
                "comment": str(data.get("comment", "")),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": summary_chars,
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Drop duplicates by unique paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # Filter out invalid rows (e.g. empty paper_id or title)
    df = df[df["paper_id"].str.strip() != ""]

    # Sort records
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
