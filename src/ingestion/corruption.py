from __future__ import annotations

from datetime import timedelta
from math import ceil
from pathlib import Path

import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: str | Path) -> pd.DataFrame:
    """Apply six reproducible faults without changing the clean input data."""
    if len(df) < 10:
        raise ValueError("At least 10 clean records are needed for the corruption suite.")

    corrupted = df.copy(deep=True).sort_values("published", ascending=False).reset_index(drop=True)
    dropped_count = ceil(len(corrupted) * 0.20)
    dropped_ids = corrupted.iloc[:dropped_count]["paper_id"].tolist()
    corrupted = corrupted.iloc[dropped_count:].copy().reset_index(drop=True)

    blank_positions = list(range(0, len(corrupted), 3))
    noise_positions = list(range(1, len(corrupted), 3))
    title_positions = list(range(2, len(corrupted), 3))
    stale_positions = list(range(0, len(corrupted), 2))

    for pos in blank_positions:
        corrupted.at[pos, "summary"] = ""
    for pos in noise_positions:
        corrupted.at[pos, "summary"] = "UNRELATED NOISE " * 12
    for pos in title_positions:
        corrupted.at[pos, "title"] = str(corrupted.at[pos, "title"])[:7]
    for pos in stale_positions:
        published = pd.Timestamp(corrupted.at[pos, "published"]) - timedelta(days=365)
        corrupted.at[pos, "published"] = published.date().isoformat()
        corrupted.at[pos, "published_date"] = published.date().isoformat()
        corrupted.at[pos, "age_days"] = int(corrupted.at[pos, "age_days"]) + 365

    for pos in range(len(corrupted)):
        row = corrupted.iloc[pos]
        summary = str(row["summary"])
        corrupted.at[pos, "summary_chars"] = len(summary)
        corrupted.at[pos, "text_for_embedding"] = (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {summary}"
        )

    duplicate_positions = [0, 1]
    duplicated_ids = corrupted.iloc[duplicate_positions]["paper_id"].tolist()
    corrupted = pd.concat([corrupted, corrupted.iloc[duplicate_positions].copy()], ignore_index=True)

    log = {
        "input_rows": len(df),
        "output_rows": len(corrupted),
        "faults": {
            "drop_latest_records": {"count": len(dropped_ids), "paper_ids": dropped_ids},
            "blank_summary": {"count": len(blank_positions), "paper_ids": corrupted.iloc[blank_positions]["paper_id"].tolist()},
            "inject_noise": {"count": len(noise_positions), "paper_ids": corrupted.iloc[noise_positions]["paper_id"].tolist()},
            "truncate_title": {"count": len(title_positions), "paper_ids": corrupted.iloc[title_positions]["paper_id"].tolist()},
            "stale_date": {"count": len(stale_positions), "paper_ids": corrupted.iloc[stale_positions]["paper_id"].tolist()},
            "duplicate_rows": {"count": len(duplicated_ids), "paper_ids": duplicated_ids},
        },
    }
    write_json(Path(output_log_path), log)
    return corrupted
