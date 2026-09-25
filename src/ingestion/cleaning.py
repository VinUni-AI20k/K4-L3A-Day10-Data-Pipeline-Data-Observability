from datetime import datetime, timezone

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


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
    6. Return clean dataframe.
    """
    rows = []
    run_dt = run_date if run_date.tzinfo else run_date.replace(tzinfo=timezone.utc)

    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        if not paper_id or not title:
            continue

        authors = [normalize_whitespace(a) for a in record.authors if a]
        authors_joined = compact_join(authors, ", ")

        categories = [normalize_whitespace(c) for c in record.categories if c]
        categories_joined = compact_join(categories, ", ")

        published = str(record.published)[:10]
        try:
            pub_dt = datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            age_days = max(0, (run_dt - pub_dt).days)
        except Exception:
            age_days = 0

        updated = str(record.updated)[:10] if record.updated else published

        text_for_embedding = f"""Title: {title}
Authors: {authors_joined}
Published: {published}
Categories: {categories_joined}
Summary: {summary}""".strip()

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": record.primary_category or (categories[0] if categories else "General"),
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "summary_chars": len(summary),
                "abs_url": record.abs_url,
                "pdf_url": record.pdf_url,
                "comment": record.comment,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["paper_id"], keep="first").reset_index(drop=True)
    return df

