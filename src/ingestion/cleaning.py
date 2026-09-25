from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord
from core.utils import normalize_whitespace


<<<<<<< HEAD
def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a deduplicated, embedding-ready dataframe.
=======
def build_clean_dataframe(raw_records: list[dict | PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize records and build embedding content with publication age.
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)

    Skip records without an ID, title or valid publication date. Keep the first
    valid record per paper_id and sort by ID for reproducible output.
    Age uses calendar dates in the supplied run_date, without UTC conversion.
    """
<<<<<<< HEAD
    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "abs_url", "pdf_url", "comment", "authors_joined",
        "categories_joined", "summary_chars", "age_days", "text_for_embedding",
    ]
    rows = []
    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize("UTC")
    else:
        run_timestamp = run_timestamp.tz_convert("UTC")

    for record in records:
        paper_id = normalize_whitespace(record.paper_id).lower()
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        authors = [normalize_whitespace(value) for value in record.authors if normalize_whitespace(value)]
        categories = [normalize_whitespace(value) for value in record.categories if normalize_whitespace(value)]
        published = pd.to_datetime(record.published, utc=True, errors="coerce")
        updated = pd.to_datetime(record.updated, utc=True, errors="coerce")
        if not paper_id or not title or pd.isna(published):
            continue

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        published_iso = published.date().isoformat()
        text_for_embedding = "\n".join([
            f"Title: {title}",
            f"Authors: {authors_joined}",
            f"Published: {published_iso}",
            f"Categories: {categories_joined}",
            f"Summary: {summary}",
        ])
        rows.append({
            "paper_id": paper_id,
            "title": title,
            "summary": summary,
            "authors": authors,
            "categories": categories,
            "primary_category": normalize_whitespace(record.primary_category),
            "published": published,
            "updated": updated if not pd.isna(updated) else published,
            "abs_url": normalize_whitespace(record.abs_url),
            "pdf_url": normalize_whitespace(record.pdf_url),
            "comment": normalize_whitespace(record.comment),
            "authors_joined": authors_joined,
            "categories_joined": categories_joined,
            "summary_chars": len(summary),
            "age_days": (run_timestamp.date() - published.date()).days,
            "text_for_embedding": text_for_embedding,
        })

    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .drop_duplicates(subset=["paper_id"], keep="first")
        .sort_values(["published", "paper_id"], ascending=[False, True])
=======
    run_timestamp = pd.Timestamp(run_date)
    if pd.isna(run_timestamp):
        raise ValueError("run_date must be a valid datetime")
    def clean_text(value: str) -> str:
        return normalize_whitespace(value or "")

    rows = []
    for record in raw_records:
        row = asdict(record) if isinstance(record, PaperRecord) else dict(record)
        row["paper_id"] = clean_text(row.get("paper_id", "")).lower()
        row["title"] = clean_text(row.get("title", ""))
        row["summary"] = clean_text(row.get("summary", ""))
        published = pd.to_datetime(row.get("published", ""), errors="coerce")
        if not row["paper_id"] or not row["title"] or pd.isna(published):
            continue
        updated = pd.to_datetime(row.get("updated", ""), errors="coerce", utc=True)
        row["published"] = published.date().isoformat()
        row["updated"] = updated.date().isoformat() if pd.notna(updated) else ""
        row["age_days"] = (run_timestamp.date() - published.date()).days
        for column in ("authors", "categories"):
            values = row.get(column) or []
            if isinstance(values, str):
                values = values.split(",")
            row[column] = [clean_text(value) for value in values if clean_text(value)]
            if column == "authors" and not row[column]:
                row[column] = ["Unknown"]
            row[f"{column}_joined"] = ", ".join(row[column])
        row["primary_category"] = row["categories"][0] if row["categories"] else ""
        row["summary_chars"] = len(row["summary"])
        row["text_for_embedding"] = (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        )
        rows.append(row)

    columns = [field.name for field in fields(PaperRecord)] + [
        "age_days", "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]
    dataframe = pd.DataFrame(rows, columns=columns)
    dataframe = dataframe.astype({"age_days": "int64", "summary_chars": "int64"})
    return (
        dataframe.drop_duplicates(subset="paper_id", keep="first")
        .sort_values("paper_id")
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
        .reset_index(drop=True)
    )
