from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records

logger = logging.getLogger(__name__)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Simulate 6 data corruption scenarios on a clean DataFrame.

    Scenarios:
    1. Drop latest records: Drop newest 20% records.
    2. Blank summary: Clear summary on selected rows.
    3. Inject noise: Add random noise/gibberish to summary.
    4. Truncate title: Shorten title to < 8 chars.
    5. Stale date: Shift published date back 365 days.
    6. Duplicate rows: Duplicate selected rows.

    Saves corruption audit log to output_log_path.
    """
    if df.empty:
        return df.copy()

    cdf = df.copy()
    corruption_logs: list[dict[str, Any]] = []

    # 1. Drop latest records (20% newest)
    if "published" in cdf.columns:
        cdf = cdf.sort_values("published", ascending=False).reset_index(drop=True)
        drop_count = max(1, int(len(cdf) * 0.20))
        dropped_ids = cdf.iloc[:drop_count]["paper_id"].tolist()
        cdf = cdf.iloc[drop_count:].reset_index(drop=True)
        corruption_logs.append({
            "scenario": "drop_latest_records",
            "description": f"Dropped newest {drop_count} records",
            "affected_count": drop_count,
            "paper_ids": dropped_ids,
        })

    # 2. Blank summary (empty summary on first 2 remaining rows)
    if len(cdf) >= 2 and "summary" in cdf.columns:
        target_ids = [cdf.loc[0, "paper_id"], cdf.loc[1, "paper_id"]]
        cdf.loc[0, "summary"] = ""
        cdf.loc[1, "summary"] = ""
        corruption_logs.append({
            "scenario": "blank_summary",
            "description": "Blanked summary field",
            "affected_count": len(target_ids),
            "paper_ids": target_ids,
        })

    # 3. Inject noise (inject garbage noise into summary of rows 2 & 3)
    if len(cdf) >= 4 and "summary" in cdf.columns:
        target_ids = [cdf.loc[2, "paper_id"], cdf.loc[3, "paper_id"]]
        noise = " ### CORRUPTED_NOISE_GIBBERISH_12345 ### "
        cdf.loc[2, "summary"] = str(cdf.loc[2, "summary"]) + noise
        cdf.loc[3, "summary"] = str(cdf.loc[3, "summary"]) + noise
        corruption_logs.append({
            "scenario": "inject_noise",
            "description": "Injected garbage noise into summary",
            "affected_count": len(target_ids),
            "paper_ids": target_ids,
        })

    # 4. Truncate title (shorten title < 8 chars on rows 4 & 5)
    if len(cdf) >= 6 and "title" in cdf.columns:
        target_ids = [cdf.loc[4, "paper_id"], cdf.loc[5, "paper_id"]]
        cdf.loc[4, "title"] = "Short"
        cdf.loc[5, "title"] = "Bad"
        corruption_logs.append({
            "scenario": "truncate_title",
            "description": "Truncated title to < 8 chars",
            "affected_count": len(target_ids),
            "paper_ids": target_ids,
        })

    # 5. Stale date (shift published date back 365 days on rows 6, 7, 8)
    if len(cdf) >= 9 and "published" in cdf.columns:
        target_ids = []
        for idx in range(6, 9):
            paper_id = cdf.loc[idx, "paper_id"]
            target_ids.append(paper_id)
            pub_str = str(cdf.loc[idx, "published"])
            try:
                dt = pd.to_datetime(pub_str) - pd.Timedelta(days=365)
                cdf.loc[idx, "published"] = dt.strftime("%Y-%m-%d")
                if "age_days" in cdf.columns:
                    cdf.loc[idx, "age_days"] = int(cdf.loc[idx, "age_days"]) + 365
            except Exception:
                pass
        corruption_logs.append({
            "scenario": "stale_date",
            "description": "Shifted published date back by 365 days",
            "affected_count": len(target_ids),
            "paper_ids": target_ids,
        })

    # 6. Duplicate rows (duplicate first 2 rows)
    if len(cdf) >= 2:
        dup_rows = cdf.iloc[:2].copy()
        duplicated_ids = dup_rows["paper_id"].tolist()
        cdf = pd.concat([cdf, dup_rows], ignore_index=True)
        corruption_logs.append({
            "scenario": "duplicate_rows",
            "description": "Duplicated rows to create duplicate paper_ids",
            "affected_count": len(dup_rows),
            "paper_ids": duplicated_ids,
        })

    # Rebuild helper fields & text_for_embedding
    cdf["summary_chars"] = cdf["summary"].apply(lambda s: len(str(s)) if pd.notna(s) else 0)

    def build_text_for_embedding(row: pd.Series) -> str:
        t = str(row.get("title", "")).strip()
        a = str(row.get("authors_joined", "")).strip()
        p = str(row.get("published", "")).strip()
        c = str(row.get("categories_joined", "")).strip()
        s = str(row.get("summary", "")).strip()
        return f"Title: {t}\nAuthors: {a}\nPublished: {p}\nCategories: {c}\nSummary: {s}"

    cdf["text_for_embedding"] = cdf.apply(build_text_for_embedding, axis=1)

    # Save corruption log
    out_path = Path(output_log_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_corruptions": len(corruption_logs),
            "corrupted_rows_final": len(cdf),
            "scenarios": corruption_logs,
        }, f, ensure_ascii=False, indent=2)

    logger.info("Corrupted dataframe created with %d rows. Log saved to %s", len(cdf), out_path)
    return cdf


def repair_clean_dataframe(raw_records_path: Path | str, run_date: datetime | None = None) -> pd.DataFrame:
    """Idempotently repair dataset by re-reading raw records and running cleaning pipeline.

    Guarantees clean 100% state without manual editing (Idempotent Repair).
    """
    raw_path = Path(raw_records_path)
    if run_date is None:
        run_date = datetime.now(timezone.utc)

    records = load_raw_records(raw_path)
    repaired_df = build_clean_dataframe(records, run_date)
    return repaired_df

