from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.config import Settings
from ingestion.crossref import PaperRecord, load_raw_records


def _clean_str(text: Any) -> str:
    """Normalize text: strip HTML/XML tags and collapse whitespace."""
    if not text:
        return ""
    # Strip HTML / JATS XML tags if present
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    # Normalize multiple whitespace characters
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records into a standardized DataFrame ready for embedding and indexing."""
    if not records:
        return pd.DataFrame(
            columns=[
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
        )

    # 1. Convert records to DataFrame
    df = pd.DataFrame([asdict(r) for r in records])

    # 2. Normalize text fields
    df["paper_id"] = df["paper_id"].astype(str).str.strip()
    df["title"] = df["title"].apply(_clean_str)
    df["summary"] = df["summary"].apply(_clean_str)

    # 3. Deduplicate by unique key paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # 4. Helper columns: joined authors, categories, summary character count
    df["authors_joined"] = df["authors"].apply(
        lambda a: ", ".join(str(x).strip() for x in a if str(x).strip())
        if isinstance(a, list)
        else str(a or "").strip()
    )
    df["categories_joined"] = df["categories"].apply(
        lambda c: ", ".join(str(x).strip() for x in c if str(x).strip())
        if isinstance(c, list)
        else str(c or "").strip()
    )
    df["summary_chars"] = df["summary"].astype(str).str.len()

    # 5. Compute age_days = (run_date - published).days
    run_dt = run_date if run_date.tzinfo else run_date.replace(tzinfo=timezone.utc)
    pub_dt = pd.to_datetime(df["published"], errors="coerce", utc=True)
    df["age_days"] = (run_dt - pub_dt).dt.days.fillna(0).astype(int)

    # 6. Compose structured text_for_embedding
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

    # 7. Filter out invalid rows (missing title or empty summary)
    df = df[df["paper_id"].str.len() > 0]
    df = df[df["title"].str.len() > 0]
    df = df[df["summary"].str.len() > 0]

    # 8. Sort deterministically and reset index
    df = df.sort_values(by="paper_id").reset_index(drop=True)
    return df


def save_clean_dataframe(
    df: pd.DataFrame, settings: Settings, stage: str = "clean"
) -> tuple[Path, Path]:
    """Persist clean DataFrame to CSV and JSON formats."""
    if stage == "clean":
        csv_path = settings.paths.clean_csv
        json_path = settings.paths.clean_json
    elif stage == "corrupted":
        csv_path = settings.paths.corrupted_clean_csv
        json_path = settings.paths.corrupted_clean_json
    elif stage == "repaired":
        csv_path = settings.paths.repaired_clean_csv
        json_path = settings.paths.repaired_clean_json
    else:
        csv_path = settings.paths.clean_csv.parent / f"papers_{stage}.csv"
        json_path = settings.paths.clean_json.parent / f"papers_{stage}.json"

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_json(json_path, orient="records", indent=2, force_ascii=False)
    return csv_path, json_path


def repair_from_raw(
    settings: Settings, run_date: datetime | None = None
) -> pd.DataFrame:
    """Idempotent Repair: Re-run cleaning pipeline directly from pristine raw records."""
    target_date = run_date or datetime.now(timezone.utc)
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, target_date)
    save_clean_dataframe(repaired_df, settings, stage="repaired")
    return repaired_df
