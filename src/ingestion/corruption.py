from __future__ import annotations

from datetime import timedelta
from math import ceil
from typing import Any

import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate realistic data failures and persist a detailed corruption log."""
    if df.empty:
        write_json(output_log_path, {"scenarios": [], "input_rows": 0, "output_rows": 0})
        return df.copy()

    corrupted = df.copy().sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    log: dict[str, Any] = {
        "input_rows": int(len(df)),
        "scenarios": [],
    }

    drop_count = max(1, ceil(len(corrupted) * 0.20))
    dropped = corrupted.head(drop_count).copy()
    corrupted = corrupted.iloc[drop_count:].reset_index(drop=True)
    log["scenarios"].append(
        {
            "name": "drop_latest_records",
            "description": "Dropped the newest 20 percent of records to mimic ingestion loss.",
            "affected_count": int(len(dropped)),
            "paper_ids": dropped["paper_id"].tolist(),
        }
    )

    blank_indices = list(corrupted.head(min(3, len(corrupted))).index)
    if blank_indices:
        corrupted.loc[blank_indices, "summary"] = ""
        corrupted.loc[blank_indices, "summary_chars"] = 0
    log["scenarios"].append(
        {
            "name": "blank_summary",
            "description": "Blanked summaries so quality checks and answers lose core evidence.",
            "affected_count": len(blank_indices),
            "paper_ids": corrupted.loc[blank_indices, "paper_id"].tolist() if blank_indices else [],
        }
    )

    noise_indices = list(corrupted.iloc[3: 3 + min(3, max(0, len(corrupted) - 3))].index)
    noise = " @@NOISE@@ ### BROKEN_TOKEN_STREAM ###"
    for idx in noise_indices:
        corrupted.at[idx, "summary"] = f"{corrupted.at[idx, 'summary']} {noise}"
        corrupted.at[idx, "summary_chars"] = len(str(corrupted.at[idx, "summary"]))
    log["scenarios"].append(
        {
            "name": "inject_noise",
            "description": "Injected junk tokens into summaries to dilute semantic retrieval.",
            "affected_count": len(noise_indices),
            "paper_ids": corrupted.loc[noise_indices, "paper_id"].tolist() if noise_indices else [],
            "noise": noise.strip(),
        }
    )

    title_indices = list(corrupted.iloc[6: 6 + min(4, max(0, len(corrupted) - 6))].index)
    for idx in title_indices:
        corrupted.at[idx, "title"] = str(corrupted.at[idx, "title"])[:6]
    log["scenarios"].append(
        {
            "name": "truncate_title",
            "description": "Truncated titles below eight characters to break exact title lookup.",
            "affected_count": len(title_indices),
            "paper_ids": corrupted.loc[title_indices, "paper_id"].tolist() if title_indices else [],
        }
    )

    stale_count = min(max(6, ceil(len(corrupted) * 0.35)), len(corrupted))
    stale_indices = list(corrupted.head(stale_count).index)
    for idx in stale_indices:
        published = pd.to_datetime(corrupted.at[idx, "published"], utc=True, errors="coerce")
        if not pd.isna(published):
            stale_date = (published - timedelta(days=365)).date().isoformat()
            corrupted.at[idx, "published"] = stale_date
            corrupted.at[idx, "updated"] = stale_date
        corrupted.at[idx, "age_days"] = int(pd.to_numeric(corrupted.at[idx, "age_days"], errors="coerce") or 0) + 365
    log["scenarios"].append(
        {
            "name": "stale_date",
            "description": "Moved a large slice of records one year into the past.",
            "affected_count": len(stale_indices),
            "paper_ids": corrupted.loc[stale_indices, "paper_id"].tolist() if stale_indices else [],
        }
    )

    duplicate_count = min(2, len(corrupted))
    duplicates = corrupted.tail(duplicate_count).copy()
    if not duplicates.empty:
        corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    log["scenarios"].append(
        {
            "name": "duplicate_rows",
            "description": "Duplicated records without changing paper_id to trigger uniqueness checks.",
            "affected_count": int(len(duplicates)),
            "paper_ids": duplicates["paper_id"].tolist(),
        }
    )

    corrupted = _rebuild_helpers(corrupted)
    log["output_rows"] = int(len(corrupted))
    log["output_duplicate_paper_ids"] = int(corrupted["paper_id"].duplicated().sum())
    log["blank_summary_rows"] = int((corrupted["summary"].fillna("") == "").sum())
    log["stale_rows"] = int((pd.to_numeric(corrupted["age_days"], errors="coerce") > 180).sum())
    write_json(output_log_path, log)
    return corrupted


def _rebuild_helpers(df: pd.DataFrame) -> pd.DataFrame:
    repaired = df.copy()
    repaired["summary"] = repaired["summary"].fillna("").astype(str)
    repaired["title"] = repaired["title"].fillna("").astype(str)
    repaired["authors_joined"] = repaired["authors_joined"].fillna("Unknown").astype(str)
    repaired["categories_joined"] = repaired["categories_joined"].fillna("Uncategorized").astype(str)
    repaired["summary_chars"] = repaired["summary"].str.len()
    repaired["text_for_embedding"] = repaired.apply(
        lambda row: (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        ),
        axis=1,
    )
    return repaired.reset_index(drop=True)
