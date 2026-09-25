from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Simulate 6 realistic data corruption scenarios to stress-test RAG & observability."""
    corrupted = df.copy()
    log: dict[str, Any] = {"scenarios": []}

    # 1. Drop latest 20% records (simulate stale ingestion / missing new data)
    n_drop = max(1, int(len(corrupted) * 0.2))
    if "published" in corrupted.columns:
        corrupted = corrupted.sort_values(by="published", ascending=False).reset_index(drop=True)
    dropped_ids = corrupted.iloc[:n_drop]["paper_id"].tolist()
    corrupted = corrupted.iloc[n_drop:].copy().reset_index(drop=True)
    log["scenarios"].append({
        "name": "drop_latest_records",
        "description": "Dropped 20% newest publications",
        "count": n_drop,
        "affected_ids": dropped_ids,
    })

    # 2. Blank summary on 2 records (simulate failed scraper / empty field)
    blank_indices = [0, 1] if len(corrupted) >= 2 else [0]
    blank_ids = []
    for idx in blank_indices:
        corrupted.loc[idx, "summary"] = ""
        corrupted.loc[idx, "summary_chars"] = 0
        blank_ids.append(corrupted.loc[idx, "paper_id"])
    log["scenarios"].append({
        "name": "blank_summary",
        "description": "Erased abstract text to empty string",
        "count": len(blank_ids),
        "affected_ids": blank_ids,
    })

    # 3. Inject noise into summary on 2 records (simulate character encoding / OCR noise)
    noise_indices = [2, 3] if len(corrupted) >= 4 else []
    noise_ids = []
    for idx in noise_indices:
        corrupted.loc[idx, "summary"] = (
            "### NOISE CORRUPTION ERROR: %%$$#*@! INVALID_TOKEN_STREAM ### "
            + str(corrupted.loc[idx, "summary"])
        )
        noise_ids.append(corrupted.loc[idx, "paper_id"])
    log["scenarios"].append({
        "name": "inject_noise",
        "description": "Injected gibberish tokens into abstract",
        "count": len(noise_ids),
        "affected_ids": noise_ids,
    })

    # 4. Truncate title to < 8 chars on 2 records (simulate truncated metadata)
    trunc_indices = [4, 5] if len(corrupted) >= 6 else []
    trunc_ids = []
    for idx in trunc_indices:
        corrupted.loc[idx, "title"] = str(corrupted.loc[idx, "title"])[:5]
        trunc_ids.append(corrupted.loc[idx, "paper_id"])
    log["scenarios"].append({
        "name": "truncate_title",
        "description": "Truncated title length to under 8 characters",
        "count": len(trunc_ids),
        "affected_ids": trunc_ids,
    })

    # 5. Stale date: shift publication back by 365 days on 40% of records (simulate outdated corpus)
    stale_count = max(1, int(len(corrupted) * 0.4))
    stale_ids = []
    for idx in range(stale_count):
        pub_val = pd.to_datetime(corrupted.loc[idx, "published"]) - pd.Timedelta(days=365)
        corrupted.loc[idx, "published"] = pub_val.strftime("%Y-%m-%d")
        if "age_days" in corrupted.columns:
            corrupted.loc[idx, "age_days"] = int(corrupted.loc[idx, "age_days"]) + 365
        stale_ids.append(corrupted.loc[idx, "paper_id"])
    log["scenarios"].append({
        "name": "stale_date",
        "description": "Shifted publication date back by 365 days",
        "count": len(stale_ids),
        "affected_ids": stale_ids,
    })

    # 6. Duplicate rows: duplicate 2 records (simulate duplicate ingestion)
    dup_rows = corrupted.iloc[:2].copy()
    corrupted = pd.concat([corrupted, dup_rows], ignore_index=True)
    log["scenarios"].append({
        "name": "duplicate_rows",
        "description": "Duplicated existing rows to introduce duplicate paper_ids",
        "count": len(dup_rows),
        "affected_ids": dup_rows["paper_id"].tolist(),
    })

    # 7. Rebuild text_for_embedding with corrupted content
    corrupted["text_for_embedding"] = corrupted.apply(
        lambda row: (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Published: {row['published']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Summary: {row['summary']}"
        ),
        axis=1,
    )

    log["original_rows"] = len(df)
    log["corrupted_rows"] = len(corrupted)

    write_json(Path(output_log_path), log)
    return corrupted
