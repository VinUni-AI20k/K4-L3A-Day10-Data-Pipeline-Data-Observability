from __future__ import annotations

import math

import pandas as pd

from core.utils import write_json

def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path,
) -> pd.DataFrame:

    corrupted = df.copy(deep=True).reset_index(drop=True)

    log = {}

    # 1. DROP LATEST RECORDS
    published_dt = pd.to_datetime(
        corrupted["published"],
        errors="coerce",
    )

    latest_indices = (
        published_dt
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    drop_count = max(
        1,
        math.ceil(len(corrupted) * 0.20),
    )

    drop_indices = latest_indices[:drop_count]

    dropped_ids = (
        corrupted.loc[drop_indices, "paper_id"]
        .tolist()
    )

    corrupted = (
        corrupted
        .drop(index=drop_indices)
        .reset_index(drop=True)
    )

    log["drop_latest_records"] = {
        "count": len(dropped_ids),
        "paper_ids": dropped_ids,
    }

    # 2. BLANK SUMMARY
    blank_count = min(
        max(1, len(corrupted) // 8),
        len(corrupted),
    )

    blank_indices = corrupted.index[:blank_count]

    blank_ids = (
        corrupted.loc[blank_indices, "paper_id"]
        .tolist()
    )

    corrupted.loc[blank_indices, "summary"] = ""

    log["blank_summary"] = {
        "count": len(blank_ids),
        "paper_ids": blank_ids,
    }

    # 3. INJECT NOISE
    noise_start = blank_count
    noise_end = min(
        noise_start + 2,
        len(corrupted),
    )

    noise_indices = corrupted.index[
        noise_start:noise_end
    ]

    noise_ids = (
        corrupted.loc[noise_indices, "paper_id"]
        .tolist()
    )

    corrupted.loc[noise_indices, "summary"] = (
        corrupted.loc[noise_indices, "summary"]
        + " @@@ ### RANDOM_NOISE_92837 ### @@@"
    )

    log["inject_noise"] = {
        "count": len(noise_ids),
        "paper_ids": noise_ids,
    }

    # 4. TRUNCATE TITLE
    title_start = noise_end
    title_end = min(
        title_start + 2,
        len(corrupted),
    )

    title_indices = corrupted.index[
        title_start:title_end
    ]

    title_ids = (
        corrupted.loc[title_indices, "paper_id"]
        .tolist()
    )

    corrupted.loc[title_indices, "title"] = (
        corrupted.loc[title_indices, "title"]
        .str[:7]
    )

    log["truncate_title"] = {
        "count": len(title_ids),
        "paper_ids": title_ids,
    }

    # 5. STALE DATE
    stale_count = max(
        1,
        math.ceil(len(corrupted) * 0.35),
    )

    stale_indices = corrupted.index[
        -stale_count:
    ]

    stale_ids = (
        corrupted.loc[stale_indices, "paper_id"]
        .tolist()
    )

    stale_dates = (
        pd.to_datetime(
            corrupted.loc[
                stale_indices,
                "published",
            ]
        )
        - pd.Timedelta(days=365)
    )

    corrupted.loc[
        stale_indices,
        "published"
    ] = stale_dates.dt.strftime("%Y-%m-%d")

    corrupted.loc[
        stale_indices,
        "age_days"
    ] = (
        corrupted.loc[
            stale_indices,
            "age_days"
        ]
        + 365
    )

    log["stale_date"] = {
        "count": len(stale_ids),
        "paper_ids": stale_ids,
    }

    # 6. DUPLICATE ROWS
    duplicate_count = min(
        2,
        len(corrupted),
    )

    duplicates = (
        corrupted
        .iloc[:duplicate_count]
        .copy()
    )

    duplicate_ids = (
        duplicates["paper_id"]
        .tolist()
    )

    corrupted = pd.concat(
        [corrupted, duplicates],
        ignore_index=True,
    )

    log["duplicate_rows"] = {
        "count": duplicate_count,
        "paper_ids": duplicate_ids,
    }

    # REBUILD DERIVED FIELDS
    corrupted["summary_chars"] = (
        corrupted["summary"]
        .fillna("")
        .astype(str)
        .str.len()
    )

    corrupted["text_for_embedding"] = (
        "Title: "
        + corrupted["title"].fillna("").astype(str)
        + "\nAuthors: "
        + corrupted["authors_joined"].fillna("").astype(str)
        + "\nPublished: "
        + corrupted["published"].fillna("").astype(str)
        + "\nCategories: "
        + corrupted["categories_joined"].fillna("").astype(str)
        + "\nSummary: "
        + corrupted["summary"].fillna("").astype(str)
    )

    write_json(
        output_log_path,
        log,
    )

    return corrupted
