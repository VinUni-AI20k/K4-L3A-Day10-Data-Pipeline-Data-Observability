from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """TODO(student): clean raw records thanh dataframe san sang de embed.

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
    for r in records:
        authors = [normalize_whitespace(a) for a in r.authors if normalize_whitespace(a)]
        categories = [normalize_whitespace(c) for c in r.categories if normalize_whitespace(c)]
        title = normalize_whitespace(r.title)
        summary = normalize_whitespace(r.summary)
        rows.append(
            {
                "paper_id": normalize_whitespace(r.paper_id),
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(r.primary_category),
                "published": r.published,
                "updated": r.updated,
                "abs_url": r.abs_url,
                "pdf_url": r.pdf_url,
                "comment": r.comment,
                "authors_joined": compact_join(authors),
                "categories_joined": compact_join(categories),
                "summary_chars": len(summary),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    run_ts = pd.Timestamp(run_date)
    run_ts = run_ts.tz_localize("UTC") if run_ts.tzinfo is None else run_ts.tz_convert("UTC")
    df["age_days"] = (run_ts - published).dt.days

    df["text_for_embedding"] = (
        "Title: " + df["title"]
        + "\nAuthors: " + df["authors_joined"]
        + "\nPublished: " + df["published"].astype(str)
        + "\nCategories: " + df["categories_joined"]
        + "\nSummary: " + df["summary"]
    )

    df = df[(df["paper_id"] != "") & (df["title"] != "") & (df["summary"] != "") & published.notna()]
    df = df.drop_duplicates(subset="paper_id", keep="first")
    return df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
