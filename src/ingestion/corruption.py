from __future__ import annotations

from datetime import UTC, datetime, timedelta
import math
import random
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


def _sample(rng: random.Random, values: list[Any], count: int) -> list[Any]:
    return rng.sample(values, min(count, len(values))) if values else []


def _rebuild_embedding_text(row: pd.Series) -> str:
    return "\n".join(
        (
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        )
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Apply six reproducible data-quality failures and write an audit log."""
    required = {"paper_id", "title", "summary", "published", "age_days", "text_for_embedding"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(sorted(missing))}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    rng = random.Random(42)
    changes: list[dict[str, Any]] = []

    # 1. Drop the newest 20% by publication date.
    drop_count = min(len(corrupted) - 1, max(1, math.ceil(len(corrupted) * 0.20))) if len(corrupted) > 1 else 0
    latest_indices = (
        corrupted.assign(_published=pd.to_datetime(corrupted["published"], errors="coerce"))
        .sort_values(["_published", "paper_id"], ascending=[False, True], kind="stable")
        .head(drop_count)
        .index.tolist()
    )
    dropped_ids = corrupted.loc[latest_indices, "paper_id"].astype(str).tolist()
    corrupted = corrupted.drop(index=latest_indices).reset_index(drop=True)
    changes.append({"type": "drop_latest_records", "count": len(dropped_ids), "paper_ids": dropped_ids, "fraction": 0.20})

    remaining = corrupted.index.tolist()
    available = remaining.copy()
    # 2. Blank summaries on 20% of surviving rows.
    blank_indices = _sample(rng, available, max(1, math.ceil(len(remaining) * 0.20)))
    available = [index for index in available if index not in blank_indices]
    for index in blank_indices:
        corrupted.at[index, "summary"] = ""
    changes.append({
        "type": "blank_summary", "count": len(blank_indices),
        "paper_ids": corrupted.loc[blank_indices, "paper_id"].astype(str).tolist(),
    })

    # 3. Add unmistakable garbage text to three rows.
    noise_indices = _sample(rng, available, 3)
    available = [index for index in available if index not in noise_indices]
    for index in noise_indices:
        current = str(corrupted.at[index, "summary"] or "").strip()
        corrupted.at[index, "summary"] = f"{current} ###CORRUPTED_GARBAGE_NOISE###".strip()
    changes.append({
        "type": "inject_noise", "count": len(noise_indices),
        "paper_ids": corrupted.loc[noise_indices, "paper_id"].astype(str).tolist(),
        "marker": "###CORRUPTED_GARBAGE_NOISE###",
    })

    # 4. Truncate titles to five characters so title-length expectations fail.
    title_indices = _sample(rng, available, 3)
    available = [index for index in available if index not in title_indices]
    for index in title_indices:
        corrupted.at[index, "title"] = str(corrupted.at[index, "title"])[:5]
    changes.append({
        "type": "truncate_title", "count": len(title_indices),
        "paper_ids": corrupted.loc[title_indices, "paper_id"].astype(str).tolist(), "max_title_chars": 5,
    })

    # 5. Make three rows older than the 180-day freshness SLA.
    stale_indices = _sample(rng, available, 3)
    available = [index for index in available if index not in stale_indices]
    stale_day = datetime.now(UTC).date() - timedelta(days=365)
    for index in stale_indices:
        corrupted.at[index, "published"] = stale_day.isoformat()
        corrupted.at[index, "age_days"] = 365
    changes.append({
        "type": "stale_date", "count": len(stale_indices),
        "paper_ids": corrupted.loc[stale_indices, "paper_id"].astype(str).tolist(),
        "published": stale_day.isoformat(), "age_days": 365,
    })

    # 6. Append copies of three surviving records to create duplicate IDs.
    duplicate_indices = _sample(rng, available, 3)
    duplicates = corrupted.loc[duplicate_indices].copy(deep=True)
    duplicated_ids = duplicates["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicates], ignore_index=True)
    changes.append({"type": "duplicate_rows", "count": len(duplicated_ids), "paper_ids": duplicated_ids})

    corrupted["summary_chars"] = corrupted["summary"].fillna("").astype(str).str.len()
    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_embedding_text, axis=1)
    log = {
        "created_at": datetime.now(UTC).isoformat(),
        "seed": 42,
        "rows_before": int(len(df)),
        "rows_after": int(len(corrupted)),
        "corruptions": changes,
    }
    write_json(Path(output_log_path), log)
    return corrupted
