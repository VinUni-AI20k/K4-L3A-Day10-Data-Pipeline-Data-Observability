from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from html import unescape
import re

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Return a deterministic, embedding-ready dataframe from raw papers.

    Invalid records are excluded rather than allowed to reach the vector index:
    a paper needs an identifier, title, summary, and parseable publication date.
    """

    columns = [
        "paper_id",
        "title",
        "summary",
        "authors",
        "categories",
        "primary_category",
        "published",
        "updated",
        "abs_url",
        "pdf_url",
        "comment",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "age_days",
        "text_for_embedding",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    def clean_text(value: object) -> str:
        if not isinstance(value, str):
            return ""
        without_tags = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", unescape(without_tags)).strip()

    def clean_list(value: object) -> list[str]:
        values = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in values:
            text = clean_text(item)
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    df = pd.DataFrame([asdict(record) for record in records])
    for column in ("paper_id", "title", "summary", "primary_category", "abs_url", "pdf_url", "comment"):
        df[column] = df[column].map(clean_text)
    df["paper_id"] = df["paper_id"].str.lower()
    df["authors"] = df["authors"].map(clean_list)
    df["categories"] = df["categories"].map(clean_list)
    df["primary_category"] = df.apply(
        lambda row: row["primary_category"] or (row["categories"][0] if row["categories"] else ""), axis=1
    )

    published_at = pd.to_datetime(df["published"], errors="coerce", utc=True)
    updated_at = pd.to_datetime(df["updated"], errors="coerce", utc=True)
    # A missing update timestamp means the publication date is the best known
    # version timestamp for the record.
    updated_at = updated_at.fillna(published_at)
    df = df.assign(_published_at=published_at, _updated_at=updated_at)
    df = df.dropna(subset=["_published_at"])
    df = df[(df["paper_id"] != "") & (df["title"] != "") & (df["summary"] != "")]
    df = df.drop_duplicates(subset="paper_id", keep="first").copy()

    if df.empty:
        return pd.DataFrame(columns=columns)

    run_at = pd.Timestamp(run_date)
    if run_at.tzinfo is None:
        run_at = run_at.tz_localize("UTC")
    else:
        run_at = run_at.tz_convert("UTC")
    run_at = run_at.normalize()

    df["published"] = df["_published_at"].dt.strftime("%Y-%m-%d")
    df["updated"] = df["_updated_at"].dt.strftime("%Y-%m-%d")
    df["authors_joined"] = df["authors"].map(
        lambda authors: ", ".join(authors) if authors else "Unknown"
    )
    df["categories_joined"] = df["categories"].map(
        lambda categories: ", ".join(categories) if categories else "Uncategorized"
    )
    df["summary_chars"] = df["summary"].str.len().astype("int64")
    df["age_days"] = (run_at - df["_published_at"].dt.normalize()).dt.days.astype("int64")
    df["text_for_embedding"] = df.apply(
        lambda row: (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        ),
        axis=1,
    )

    return (
        df.drop(columns=["_published_at", "_updated_at"])
        .sort_values(["published", "paper_id"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)[columns]
    )
