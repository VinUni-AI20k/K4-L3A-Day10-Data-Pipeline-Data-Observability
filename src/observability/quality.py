from __future__ import annotations

from typing import Any

import great_expectations as gx
from great_expectations import expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROWS, MAX_ROWS = 5, 5000
MIN_SUMMARY_CHARS = 30
MAX_STALE_RATIO = 0.25


def _stale_stats(df: pd.DataFrame, settings: Settings) -> tuple[int, float]:
    stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum()) if len(df) else 0
    ratio = stale_rows / len(df) if len(df) else 0.0
    return stale_rows, ratio


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS),
        gxe.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="title"),
        gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
    ]

    checks = []
    for expectation in expectations:
        result = batch.validate(expectation)
        checks.append(
            {
                "expectation": type(expectation).__name__,
                "column": getattr(expectation, "column", None),
                "success": bool(result.success),
                "result": {k: v for k, v in result.result.items() if k in {"observed_value", "unexpected_count", "element_count"}},
            }
        )

    stale_rows, stale_ratio = _stale_stats(df, settings)
    checks.append(
        {
            "expectation": "FreshnessCheck",
            "column": "age_days",
            "success": stale_ratio <= MAX_STALE_RATIO,
            "result": {
                "stale_rows": stale_rows,
                "stale_ratio": round(stale_ratio, 4),
                "threshold_days": settings.freshness_threshold_days,
                "max_stale_ratio": MAX_STALE_RATIO,
            },
        }
    )

    report = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "success": all(c["success"] for c in checks),
        "total_rows": int(len(df)),
        "passed": sum(c["success"] for c in checks),
        "failed": sum(not c["success"] for c in checks),
        "checks": checks,
    }
    write_json(settings.paths.quality_dir / f"{report_name}.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    stale_rows, stale_ratio = _stale_stats(df, settings)
    payload = {
        "latest_published": published.max().date().isoformat() if len(df) else None,
        "oldest_published": published.min().date().isoformat() if len(df) else None,
        "stale_rows": stale_rows,
        "total_rows": int(len(df)),
        "is_fresh": stale_ratio <= MAX_STALE_RATIO,
    }
    write_json(report_path, payload)
    return payload
