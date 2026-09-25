from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "published",
    "age_days",
    "text_for_embedding",
}
_NOISE = "ZXQJ_9x7v !!! @@@ ### $$$ %%% ^^^ ZXQJ_9x7v"


def _scenario_size(row_count: int, ratio: float) -> int:
    """Return a non-zero sample size when there are rows to corrupt."""
    return min(row_count, max(1, ceil(row_count * ratio))) if row_count else 0


def _take_cyclic(indices: list[Any], start: int, count: int) -> list[Any]:
    """Select deterministic positions and gracefully handle tiny dataframes."""
    if not indices or count <= 0:
        return []
    return [indices[(start + offset) % len(indices)] for offset in range(count)]


def _as_text(value: Any, default: str) -> str:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text or default


def _rebuild_embedding_text(row: pd.Series) -> str:
    """Rebuild the canonical vector text after structured fields are damaged."""
    return "\n".join(
        [
            f"Title: {_as_text(row.get('title'), 'Untitled')}",
            f"Authors: {_as_text(row.get('authors_joined'), 'Unknown')}",
            f"Published: {_as_text(row.get('published'), 'Unknown')}",
            f"Categories: {_as_text(row.get('categories_joined'), 'Uncategorized')}",
            f"Summary: {_as_text(row.get('summary'), '')}",
        ]
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Inject six deterministic failure modes into an already-clean dataset.

    The input dataframe is never changed in place. The returned dataframe keeps
    the baseline schema, while the JSON log records affected document IDs for
    every scenario so a later repair/evaluation pass can audit the damage.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    missing_columns = sorted(_REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(
            "Clean dataframe is missing required columns: "
            + ", ".join(missing_columns)
        )

    corrupted = df.copy(deep=True).reset_index(drop=True)
    input_rows = len(corrupted)
    events: list[dict[str, Any]] = []

    # 1. Remove the newest 20% according to the publication timestamp.
    drop_count = _scenario_size(input_rows, 0.20)
    published_dates = pd.to_datetime(
        corrupted["published"], errors="coerce", utc=True
    )
    drop_indices = list(
        published_dates.sort_values(ascending=False, na_position="last")
        .index[:drop_count]
    )
    dropped_rows = corrupted.loc[drop_indices, ["paper_id", "published"]]
    events.append(
        {
            "type": "drop_latest_records",
            "count": len(drop_indices),
            "paper_ids": dropped_rows["paper_id"].astype(str).tolist(),
            "original_published": dropped_rows["published"].astype(str).tolist(),
            "description": "Removed the newest 20% of source records.",
        }
    )
    corrupted = corrupted.drop(index=drop_indices).reset_index(drop=True)

    remaining_indices = corrupted.index.tolist()
    remaining_rows = len(remaining_indices)
    blank_count = _scenario_size(remaining_rows, 0.15)
    noise_count = _scenario_size(remaining_rows, 0.15)
    title_count = _scenario_size(remaining_rows, 0.15)
    stale_count = _scenario_size(remaining_rows, 0.40)
    duplicate_count = _scenario_size(remaining_rows, 0.10)

    cursor = 0
    blank_indices = _take_cyclic(remaining_indices, cursor, blank_count)
    cursor += blank_count
    noise_indices = _take_cyclic(remaining_indices, cursor, noise_count)
    cursor += noise_count
    title_indices = _take_cyclic(remaining_indices, cursor, title_count)
    cursor += title_count
    stale_indices = _take_cyclic(remaining_indices, cursor, stale_count)
    cursor += stale_count
    duplicate_indices = _take_cyclic(remaining_indices, cursor, duplicate_count)

    # 2. Blank summaries and keep the derived character count consistent.
    corrupted.loc[blank_indices, "summary"] = ""
    if "summary_chars" in corrupted.columns:
        corrupted.loc[blank_indices, "summary_chars"] = 0
    events.append(
        {
            "type": "blank_summary",
            "count": len(blank_indices),
            "paper_ids": corrupted.loc[blank_indices, "paper_id"].astype(str).tolist(),
            "description": "Replaced selected summaries with empty strings.",
        }
    )

    # 3 is applied after rebuilding canonical vector text below, ensuring the
    # meaningless payload is not accidentally overwritten.

    # 4. Seven characters is deliberately below both requested limits (<10 and
    # the lab guide's stricter <8 condition).
    original_titles = corrupted.loc[title_indices, "title"].astype(str).tolist()
    corrupted.loc[title_indices, "title"] = (
        corrupted.loc[title_indices, "title"].astype(str).str.slice(0, 7)
    )
    events.append(
        {
            "type": "truncate_title",
            "count": len(title_indices),
            "paper_ids": corrupted.loc[title_indices, "paper_id"].astype(str).tolist(),
            "original_titles": original_titles,
            "description": "Truncated selected titles to at most seven characters.",
        }
    )

    # 5. Shift publication dates back by exactly five calendar years. Adjusting
    # age_days by the same delta lets the freshness gate observe the corruption.
    old_published = pd.to_datetime(
        corrupted.loc[stale_indices, "published"], errors="coerce", utc=True
    )
    stale_published = old_published.map(
        lambda value: value - pd.DateOffset(years=5) if pd.notna(value) else value
    )
    date_deltas = (old_published - stale_published).dt.days
    old_ages = pd.to_numeric(
        corrupted.loc[stale_indices, "age_days"], errors="coerce"
    )
    corrupted.loc[stale_indices, "published"] = stale_published.map(
        lambda value: value.date().isoformat() if pd.notna(value) else ""
    )
    corrupted.loc[stale_indices, "age_days"] = (
        old_ages.fillna(0) + date_deltas.fillna(0)
    ).astype(int)
    events.append(
        {
            "type": "stale_date",
            "count": len(stale_indices),
            "paper_ids": corrupted.loc[stale_indices, "paper_id"].astype(str).tolist(),
            "years_shifted": 5,
            "description": "Shifted selected publication dates five years into the past.",
        }
    )

    # Rebuild all documents so blank summaries, truncated titles and stale dates
    # are faithfully represented in the vector database input.
    corrupted["text_for_embedding"] = corrupted.apply(
        _rebuild_embedding_text, axis=1
    )

    # 3. Inject high-density meaningless tokens directly into vector content.
    corrupted.loc[noise_indices, "text_for_embedding"] = (
        corrupted.loc[noise_indices, "text_for_embedding"].astype(str)
        + "\nNoise: "
        + (_NOISE + " ") * 8
    ).str.rstrip()
    events.insert(
        2,
        {
            "type": "inject_text_noise",
            "count": len(noise_indices),
            "paper_ids": corrupted.loc[noise_indices, "paper_id"].astype(str).tolist(),
            "noise": _NOISE,
            "description": "Appended meaningless character sequences to embedding text.",
        }
    )

    # 6. Append exact copies, preserving paper_id so the uniqueness expectation
    # fails as it would for duplicated source events.
    duplicate_rows = corrupted.loc[duplicate_indices].copy(deep=True)
    duplicated_ids = duplicate_rows["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)
    events.append(
        {
            "type": "duplicate_rows",
            "count": len(duplicate_rows),
            "paper_ids": duplicated_ids,
            "description": "Appended exact row copies with duplicate paper_id values.",
        }
    )

    log = {
        "input_rows": input_rows,
        "output_rows": len(corrupted),
        "net_row_change": len(corrupted) - input_rows,
        "scenario_count": len(events),
        "corruptions": events,
    }
    write_json(Path(output_log_path), log)
    return corrupted.reset_index(drop=True)
