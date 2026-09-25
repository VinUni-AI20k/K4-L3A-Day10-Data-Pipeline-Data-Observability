from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    checks = {
        "row_count_5_to_5000": 5 <= len(df) <= 5000,
        "paper_id_non_null": bool(df.get("paper_id", pd.Series(dtype=object)).notna().all()),
        "title_non_null": bool(df.get("title", pd.Series(dtype=object)).notna().all()),
        "text_for_embedding_non_null": bool(df.get("text_for_embedding", pd.Series(dtype=object)).notna().all()),
        "paper_id_unique": bool(df.get("paper_id", pd.Series(dtype=object)).is_unique),
        "summary_min_30_chars": bool(df.get("summary", pd.Series(dtype=object)).fillna("").str.len().ge(30).all()),
    }
    payload = {"report_name": report_name, "success": all(checks.values()), "checks": checks, "row_count": len(df)}
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    dates = pd.to_datetime(df.get("published", pd.Series(dtype=object)), errors="coerce", utc=True)
    age_days = pd.to_numeric(df.get("age_days", pd.Series(dtype=float)), errors="coerce")
    stale_rows = int(age_days.gt(settings.freshness_threshold_days).sum())
    total_rows = len(df)
    payload = {
        "latest_published": dates.max().date().isoformat() if dates.notna().any() else None,
        "oldest_published": dates.min().date().isoformat() if dates.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_rows / total_rows if total_rows else 1.0,
        "is_fresh": bool(total_rows and stale_rows / total_rows <= 0.25),
    }
    write_json(report_path, payload)
    return payload
