from __future__ import annotations

from datetime import datetime
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed."""
    rows: list[dict] = []
    run_date_val = run_date.date() if isinstance(run_date, datetime) else run_date

    for r in records:
        paper_id = normalize_whitespace(str(r.paper_id or ""))
        title = normalize_whitespace(re.sub(r"<[^>]+>", "", str(r.title or "")))
        summary = normalize_whitespace(re.sub(r"<[^>]+>", "", str(r.summary or "")))

        authors = [normalize_whitespace(a) for a in r.authors if normalize_whitespace(a)]
        authors_joined = compact_join(authors, sep=", ") if authors else "Unknown"

        categories = [normalize_whitespace(c) for c in r.categories if normalize_whitespace(c)]
        categories_joined = compact_join(categories, sep=", ") if categories else "General"
        primary_category = categories[0] if categories else (r.primary_category or "General")

        published_str = str(r.published or "").strip()[:10]
        try:
            pub_date = datetime.strptime(published_str, "%Y-%m-%d").date()
        except Exception:
            pub_date = run_date_val
            published_str = pub_date.isoformat()

        updated_str = str(r.updated or "").strip()[:10] or published_str

        age_days = max(0, (run_date_val - pub_date).days)
        summary_chars = len(summary)

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published_str}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        abs_url = str(r.abs_url or f"https://doi.org/{paper_id}")
        pdf_url = str(r.pdf_url or abs_url)
        comment = str(r.comment or f"Crossref record {paper_id}")

        if not paper_id or len(title) < 5:
            continue

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
                "published": published_str,
                "updated": updated_str,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
                "comment": comment,
                "age_days": age_days,
                "summary_chars": summary_chars,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df

