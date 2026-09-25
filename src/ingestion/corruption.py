from __future__ import annotations

<<<<<<< HEAD
import math
from pathlib import Path
=======
from datetime import datetime, timedelta
from core.compat import UTC
from pathlib import Path
from typing import Any
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)

import pandas as pd

from core.utils import write_json
<<<<<<< HEAD


NOISE = "zxqv_@@@_CORRUPTED_VECTOR_NOISE_9f8e7d_###_zxqv"


def _rebuild_embedding_text(row: pd.Series) -> str:
    published = pd.to_datetime(row.get("published"), utc=True, errors="coerce")
    published_text = published.date().isoformat() if not pd.isna(published) else ""
    return "\n".join([
        f"Title: {row.get('title', '')}",
        f"Authors: {row.get('authors_joined', '')}",
        f"Published: {published_text}",
        f"Categories: {row.get('categories_joined', '')}",
        f"Summary: {row.get('summary', '')}",
    ])


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject six deterministic data-corruption scenarios and write an audit log.
=======

NOISE = "!@#$% RANDOM NOISE CORRUPTION gibberish_token_xyz"
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Apply six deterministic, observable corruption scenarios.

    The returned frame has the same row count as the input: three newest rows
    are removed, then three existing rows are appended as duplicates. All
    changes are deterministic to make the corruption experiment reproducible.
    """
<<<<<<< HEAD
    required = {"paper_id", "title", "summary", "published", "age_days", "text_for_embedding"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {', '.join(missing)}")
    if len(df) < 10:
        raise ValueError("At least 10 rows are required for the six corruption scenarios")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    corrupted["published"] = pd.to_datetime(corrupted["published"], utc=True, errors="coerce")
    corrupted = corrupted.sort_values("published", ascending=False).reset_index(drop=True)
    original_rows = len(corrupted)
    actions: list[dict] = []

    # 1) Remove the newest 20% to simulate a source that silently stopped updating.
    drop_count = max(1, math.ceil(original_rows * 0.20))
    dropped = corrupted.iloc[:drop_count]
    actions.append({
        "scenario": "drop_latest_records",
        "description": "Removed the newest 20% of records.",
        "affected_count": int(drop_count),
        "paper_ids": dropped["paper_id"].astype(str).tolist(),
    })
    corrupted = corrupted.iloc[drop_count:].reset_index(drop=True)

    # Deterministic slices make repeated demonstrations reproducible.
    mutation_count = max(2, math.ceil(len(corrupted) * 0.15))
    blank_idx = list(range(0, min(mutation_count, len(corrupted))))
    noise_idx = list(range(mutation_count, min(2 * mutation_count, len(corrupted))))
    title_idx = list(range(2 * mutation_count, min(3 * mutation_count, len(corrupted))))

    # 2) Blank summaries and keep summary_chars consistent with the damage.
    corrupted.loc[blank_idx, "summary"] = ""
    if "summary_chars" in corrupted:
        corrupted.loc[blank_idx, "summary_chars"] = 0
    actions.append({
        "scenario": "blank_summary",
        "description": "Replaced summaries with empty strings.",
        "affected_count": len(blank_idx),
        "paper_ids": corrupted.loc[blank_idx, "paper_id"].astype(str).tolist(),
    })

    # 3) Noise is attached after the structured embedding text is rebuilt below.
    noise_ids = corrupted.loc[noise_idx, "paper_id"].astype(str).tolist()
    actions.append({
        "scenario": "inject_text_noise",
        "description": "Injected a deterministic garbage token sequence into text_for_embedding.",
        "affected_count": len(noise_idx),
        "paper_ids": noise_ids,
        "noise": NOISE,
    })

    # 4) Force visibly invalid titles shorter than ten characters.
    original_titles = corrupted.loc[title_idx, ["paper_id", "title"]].copy()
    corrupted.loc[title_idx, "title"] = corrupted.loc[title_idx, "title"].astype(str).str[:7]
    actions.append({
        "scenario": "truncate_title",
        "description": "Truncated titles to at most 7 characters.",
        "affected_count": len(title_idx),
        "records": [
            {"paper_id": str(row.paper_id), "original_title": str(row.title)}
            for row in original_titles.itertuples(index=False)
        ],
    })

    # 5) Make enough records stale for the >25% Freshness SLA to trip.
    stale_count = max(1, math.ceil(len(corrupted) * 0.35))
    stale_idx = list(range(stale_count))
    stale_before = corrupted.loc[stale_idx, ["paper_id", "published"]].copy()
    corrupted.loc[stale_idx, "published"] = (
        corrupted.loc[stale_idx, "published"] - pd.DateOffset(years=5)
    )
    corrupted.loc[stale_idx, "age_days"] = (
        pd.to_numeric(corrupted.loc[stale_idx, "age_days"], errors="coerce").fillna(0) + 1826
    ).astype(int)
    actions.append({
        "scenario": "stale_date",
        "description": "Moved publication dates five years into the past.",
        "affected_count": len(stale_idx),
        "records": [
            {"paper_id": str(row.paper_id), "original_published": row.published.isoformat()}
            for row in stale_before.itertuples(index=False)
        ],
    })

    # Rebuild structured content so blank summaries, titles and dates propagate.
    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_embedding_text, axis=1)
    corrupted.loc[noise_idx, "text_for_embedding"] = (
        corrupted.loc[noise_idx, "text_for_embedding"].astype(str) + "\nNoise: " + NOISE
    )

    # 6) Duplicate already damaged rows, preserving paper_id to violate uniqueness.
    duplicate_count = max(2, math.ceil(len(corrupted) * 0.15))
    duplicated = corrupted.iloc[:duplicate_count].copy(deep=True)
    corrupted = pd.concat([corrupted, duplicated], ignore_index=True)
    actions.append({
        "scenario": "duplicate_rows",
        "description": "Appended exact row copies with duplicate paper_id values.",
        "affected_count": int(duplicate_count),
        "paper_ids": duplicated["paper_id"].astype(str).tolist(),
    })

    log = {
        "original_rows": int(original_rows),
        "corrupted_rows": int(len(corrupted)),
        "scenario_count": len(actions),
        "actions": actions,
    }
    write_json(Path(output_log_path), log)
    return corrupted.reset_index(drop=True)
=======
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    required = {"paper_id", "title", "summary", "published", "text_for_embedding"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing corruption columns: {sorted(missing)}")
    original_count = len(df)
    corrupted = df.copy(deep=True).reset_index(drop=True)
    scenarios: list[dict[str, Any]] = []

    def record(name: str, indices: list[Any], details: str) -> None:
        scenarios.append({"name": name, "affected_count": len(indices), "details": details})

    # 1. Remove the three newest rows (or as many as safely possible).
    drop_count = min(3, max(0, len(corrupted) - 2))
    dates = pd.to_datetime(corrupted["published"], errors="coerce")
    newest = dates.sort_values(ascending=False, na_position="last").index[:drop_count].tolist()
    dropped_ids = corrupted.loc[newest, "paper_id"].astype(str).tolist()
    corrupted = corrupted.drop(index=newest).reset_index(drop=True)
    record("drop_latest_records", dropped_ids, f"Removed newest published records: {dropped_ids}")

    # Subsequent selections are disjoint where possible, so each signal is
    # visible independently in the quality report.
    def select(count: int, offset: int = 0) -> list[int]:
        if corrupted.empty:
            return []
        return [int(i) for i in corrupted.index[offset:offset + min(count, len(corrupted))]]

    blank = select(3, 0)
    corrupted.loc[blank, "summary"] = ""
    record("blank_summary", corrupted.loc[blank, "paper_id"].astype(str).tolist(),
           "Set summary to an empty string.")

    noisy = select(3, 3)
    corrupted.loc[noisy, "text_for_embedding"] = corrupted.loc[noisy, "text_for_embedding"].astype(str) + " " + NOISE
    record("inject_text_noise", corrupted.loc[noisy, "paper_id"].astype(str).tolist(),
           f"Appended noise marker: {NOISE}")

    truncated = select(3, 6)
    corrupted.loc[truncated, "title"] = corrupted.loc[truncated, "title"].astype(str).str.slice(0, 8)
    record("truncate_title", corrupted.loc[truncated, "paper_id"].astype(str).tolist(),
           "Truncated title to at most eight characters.")

    stale = select(4, 9)
    stale_date = (datetime.now(UTC).date() - timedelta(days=1825)).isoformat()
    corrupted.loc[stale, "published"] = stale_date
    if "age_days" in corrupted.columns:
        run_reference = pd.Timestamp(datetime.now(UTC).date())
        corrupted.loc[stale, "age_days"] = (run_reference - pd.Timestamp(stale_date)).days
    record("stale_date", corrupted.loc[stale, "paper_id"].astype(str).tolist(),
           f"Set published to {stale_date} and recomputed age_days.")

    # 6. Restore the original row count with duplicates. Duplicate IDs are
    # intentional and are what ExpectColumnValuesToBeUnique must catch.
    duplicate_count = min(drop_count, len(corrupted))
    duplicate_source = corrupted.iloc[:duplicate_count].copy(deep=True)
    corrupted = pd.concat([corrupted, duplicate_source], ignore_index=True)
    record("duplicate_rows", duplicate_source["paper_id"].astype(str).tolist(),
           "Appended exact copies to restore the original row count.")

    # Rebuild the composite text after summary/title/date mutations. Preserve
    # injected noise by appending it after the canonical content.
    for index in corrupted.index:
        authors = corrupted.at[index, "authors_joined"] if "authors_joined" in corrupted else corrupted.at[index, "authors"] if "authors" in corrupted else ""
        categories = corrupted.at[index, "categories_joined"] if "categories_joined" in corrupted else corrupted.at[index, "categories"] if "categories" in corrupted else ""
        corrupted.at[index, "text_for_embedding"] = (
            f"Title: {corrupted.at[index, 'title']}\n"
            f"Authors: {authors}\n"
            f"Published: {corrupted.at[index, 'published']}\n"
            f"Categories: {categories}\n"
            f"Summary: {corrupted.at[index, 'summary']}"
            + (f" {NOISE}" if NOISE in str(corrupted.at[index, "text_for_embedding"]) else "")
        )

    log = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_original_rows": original_count,
        "total_corrupted_rows": len(corrupted),
        "scenarios": scenarios,
    }
    write_json(Path(output_log_path), log)
    return corrupted
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
