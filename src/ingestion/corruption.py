from __future__ import annotations

import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply six deterministic corruption scenarios and record their lineage.

    Pseudo-code:
    1. Drop mot so latest records.
    2. Blank summary o mot so dong.
    3. Inject noise vao text.
    4. Lam title bi truncate.
    5. Lam published date cu di.
    6. Add duplicate rows.
    7. Rebuild `text_for_embedding`.
    8. Ghi corruption log vao output_log_path.
    """
    if len(df) < 10:
        raise ValueError("At least ten rows are required for the corruption suite.")
    corrupted = df.copy(deep=True).reset_index(drop=True)
    published = pd.to_datetime(corrupted["published"], errors="coerce")
    latest_indices = published.sort_values(ascending=False).index[:5].tolist()
    dropped_ids = corrupted.loc[latest_indices, "paper_id"].tolist()
    corrupted = corrupted.drop(index=latest_indices).reset_index(drop=True)

    blank_indices = list(range(min(3, len(corrupted))))
    noise_indices = list(range(3, min(6, len(corrupted))))
    title_indices = list(range(6, min(9, len(corrupted))))
    stale_indices = list(range(0, min(10, len(corrupted))))

    corrupted.loc[blank_indices, "summary"] = ""
    corrupted.loc[noise_indices, "summary"] = (
        corrupted.loc[noise_indices, "summary"].astype(str) + " ZXQ_@@@_NOISE_9999"
    )
    corrupted.loc[title_indices, "title"] = corrupted.loc[title_indices, "title"].astype(str).str[:7]
    stale_date = (pd.Timestamp.now(tz="UTC") - pd.DateOffset(years=5)).date().isoformat()
    corrupted.loc[stale_indices, "published"] = stale_date
    corrupted.loc[stale_indices, "age_days"] = 5 * 365

    def rebuild(index: int) -> None:
        row = corrupted.loc[index]
        corrupted.at[index, "summary_chars"] = len(str(row["summary"]))
        corrupted.at[index, "text_for_embedding"] = (
            f"Title: {row['title']}\nAuthors: {row['authors_joined']}\nPublished: {row['published']}\n"
            f"Categories: {row['categories_joined']}\nSummary: {row['summary']}"
        )

    for index in sorted(set(blank_indices + noise_indices + title_indices + stale_indices)):
        rebuild(index)

    duplicate_source = corrupted.head(5).copy(deep=True)
    duplicate_ids = duplicate_source["paper_id"].tolist()
    corrupted = pd.concat([corrupted, duplicate_source], ignore_index=True)
    log = {
        "scenarios": [
            {"name": "drop_latest_records", "affected_rows": len(dropped_ids), "paper_ids": dropped_ids},
            {"name": "blank_summary", "affected_rows": len(blank_indices)},
            {"name": "inject_text_noise", "affected_rows": len(noise_indices)},
            {"name": "truncate_title", "affected_rows": len(title_indices)},
            {"name": "stale_date", "affected_rows": len(stale_indices), "replacement": stale_date},
            {"name": "duplicate_rows", "affected_rows": len(duplicate_ids), "paper_ids": duplicate_ids},
        ],
        "input_rows": int(len(df)),
        "output_rows": int(len(corrupted)),
    }
    write_json(output_log_path, log)
    return corrupted
