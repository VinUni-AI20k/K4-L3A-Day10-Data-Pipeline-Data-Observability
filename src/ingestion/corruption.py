from __future__ import annotations

from datetime import UTC, datetime
import math

import pandas as pd

from core.utils import write_json


def _embedding_text(row: pd.Series) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject six deterministic failure modes while preserving row count.

    The operations deliberately target the newest documents because the fixed
    benchmark is built from that same leading window.  This makes the silent
    retrieval degradation observable and repeatable instead of probabilistic.
    """
    if len(df) < 10:
        raise ValueError("At least 10 rows are required for the corruption experiment.")
    required = {
        "paper_id",
        "title",
        "summary",
        "published",
        "authors_joined",
        "categories_joined",
        "text_for_embedding",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {', '.join(missing)}")

    original_count = len(df)
    corrupted = df.copy(deep=True)
    published = pd.to_datetime(corrupted["published"], errors="coerce")
    corrupted = corrupted.assign(_published_sort=published).sort_values(
        "_published_sort", ascending=False, kind="stable"
    )
    drop_count = max(1, math.ceil(original_count * 0.20))
    dropped_ids = corrupted.head(drop_count)["paper_id"].astype(str).tolist()
    corrupted = corrupted.iloc[drop_count:].drop(columns=["_published_sort"]).reset_index(drop=True)

    target_count = min(5, len(corrupted))
    target_indices = list(range(target_count))
    target_ids = corrupted.loc[target_indices, "paper_id"].astype(str).tolist()

    corrupted.loc[target_indices, "summary"] = ""
    corrupted.loc[target_indices, "summary_chars"] = 0

    corrupted.loc[target_indices, "title"] = corrupted.loc[target_indices, "title"].map(
        lambda value: str(value)[:7]
    )

    old_dates = pd.to_datetime(corrupted["published"], errors="coerce") - pd.DateOffset(years=5)
    corrupted["published"] = old_dates.dt.strftime("%Y-%m-%d")
    today = datetime.now(UTC).date()
    corrupted["age_days"] = old_dates.map(
        lambda value: (today - value.date()).days if not pd.isna(value) else None
    )

    corrupted["text_for_embedding"] = corrupted.apply(_embedding_text, axis=1)
    noise = " ".join(["ZXQ_CORRUPTED_VECTOR_NOISE"] * 40)
    corrupted["text_for_embedding"] = noise + "\n" + corrupted["text_for_embedding"]

    duplicate_count = original_count - len(corrupted)
    duplicate_source = corrupted.head(duplicate_count).copy(deep=True)
    duplicate_ids = duplicate_source["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicate_source], ignore_index=True)

    operations = [
        {
            "scenario": "drop_latest_records",
            "affected_rows": len(dropped_ids),
            "paper_ids": dropped_ids,
            "details": "Removed the newest 20% of source rows.",
        },
        {
            "scenario": "blank_summary",
            "affected_rows": len(target_ids),
            "paper_ids": target_ids,
            "details": "Replaced selected summaries with empty strings.",
        },
        {
            "scenario": "inject_text_noise",
            "affected_rows": len(corrupted) - duplicate_count,
            "paper_ids": corrupted.iloc[: len(corrupted) - duplicate_count]["paper_id"].astype(str).tolist(),
            "details": "Prefixed embedding text with high-volume synthetic noise.",
        },
        {
            "scenario": "truncate_title",
            "affected_rows": len(target_ids),
            "paper_ids": target_ids,
            "details": "Truncated selected titles to seven characters.",
        },
        {
            "scenario": "stale_date",
            "affected_rows": len(corrupted) - duplicate_count,
            "paper_ids": corrupted.iloc[: len(corrupted) - duplicate_count]["paper_id"].astype(str).tolist(),
            "details": "Shifted publication dates five years into the past.",
        },
        {
            "scenario": "duplicate_rows",
            "affected_rows": duplicate_count,
            "paper_ids": duplicate_ids,
            "details": "Duplicated rows to restore the original row count with non-unique IDs.",
        },
    ]
    write_json(
        output_log_path,
        {
            "original_rows": original_count,
            "corrupted_rows": len(corrupted),
            "scenario_count": len(operations),
            "operations": operations,
        },
    )
    return corrupted.reset_index(drop=True)
