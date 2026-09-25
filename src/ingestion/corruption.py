from __future__ import annotations

import pandas as pd
from datetime import timedelta
from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    corrupted = df.copy(deep=True)
    log: list[dict[str, object]] = []
    if corrupted.empty:
        write_json(output_log_path, log)
        return corrupted
    latest_count = max(1, round(len(corrupted) * 0.2))
    published_dates = pd.to_datetime(corrupted["published"], errors="coerce")
    latest_ids = published_dates.nlargest(latest_count).index
    corrupted = corrupted.drop(index=latest_ids)
    log.append({"type": "drop_latest", "rows": len(latest_ids), "paper_ids": df.loc[latest_ids, "paper_id"].tolist()})
    if not corrupted.empty:
        positions = list(corrupted.index)
        blank_index = positions[0]
        corrupted.loc[blank_index, "summary"] = ""
        log.append({"type": "blank_summary", "paper_id": corrupted.loc[blank_index, "paper_id"]})
        noise_index = positions[min(1, len(positions) - 1)]
        corrupted.loc[noise_index, "summary"] = "@@@ ### " + corrupted.loc[noise_index, "summary"]
        log.append({"type": "inject_noise", "paper_id": corrupted.loc[noise_index, "paper_id"]})
        title_index = positions[min(2, len(positions) - 1)]
        corrupted.loc[title_index, "title"] = str(corrupted.loc[title_index, "title"])[:7]
        log.append({"type": "truncate_title", "paper_id": corrupted.loc[title_index, "paper_id"]})
        date_index = positions[min(3, len(positions) - 1)]
        corrupted.loc[date_index, "published"] = (
            pd.to_datetime(corrupted.loc[date_index, "published"]) - timedelta(days=365)
        ).date().isoformat()
        log.append({"type": "stale_date", "paper_id": corrupted.loc[date_index, "paper_id"]})
    duplicate = corrupted.iloc[[0]].copy() if not corrupted.empty else corrupted.copy()
    corrupted = pd.concat([corrupted, duplicate], ignore_index=True)
    log.append({"type": "duplicate_rows", "rows": len(duplicate), "paper_ids": duplicate["paper_id"].tolist()})
    corrupted["summary_chars"] = corrupted["summary"].fillna("").str.len()
    corrupted["text_for_embedding"] = (
        "Title: " + corrupted["title"].fillna("") + "\nAuthors: " + corrupted["authors_joined"].fillna("")
        + "\nPublished: " + corrupted["published"].fillna("").astype(str)
        + "\nCategories: " + corrupted["categories_joined"].fillna("")
        + "\nSummary: " + corrupted["summary"].fillna("")
    )
    write_json(output_log_path, log)
    return corrupted
