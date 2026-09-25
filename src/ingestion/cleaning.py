from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    run_date_only = run_date.date() if hasattr(run_date, "date") else run_date
    rows = []
    for r in records:
        title = normalize_whitespace(r.title)
        summary = normalize_whitespace(r.summary)
        if not title or not summary:
            continue
        try:
            pub_date = date.fromisoformat(r.published)
            age_days = (run_date_only - pub_date).days
        except ValueError:
            age_days = -1
        authors_joined = ", ".join(r.authors)
        categories_joined = ", ".join(r.categories)
        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {r.published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )
        rows.append({
            "paper_id": r.paper_id,
            "title": title,
            "summary": summary,
            "authors": r.authors,
            "categories": r.categories,
            "primary_category": r.primary_category,
            "published": r.published,
            "updated": r.updated,
            "abs_url": r.abs_url,
            "pdf_url": r.pdf_url,
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "age_days": age_days,
            "summary_chars": len(summary),
            "text_for_embedding": text_for_embedding,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(subset="paper_id", keep="first")
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    return df
