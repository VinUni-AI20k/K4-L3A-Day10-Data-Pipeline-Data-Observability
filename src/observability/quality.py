from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Execute Great Expectations 1.x data quality checks and Freshness SLA monitoring.

    1. Initialize ephemeral GX 1.x context.
    2. Register pandas data source, data asset, and batch definition.
    3. Run 4 core expectations:
       - ExpectTableRowCountToBeBetween (5 to 5000)
       - ExpectColumnValuesToNotBeNull (paper_id, title, text_for_embedding)
       - ExpectColumnValuesToBeUnique (paper_id)
       - ExpectColumnValueLengthsToBeBetween (summary min 30 chars)
    4. Run Freshness Check (stale ratio <= 25% for age_days > 180).
    5. Save quality report JSON into `data/quality/`.
    """
    total_rows = len(df)
    results = []
    gx_success = True

    if total_rows == 0:
        gx_success = False
    else:
        context = gx.get_context(mode="ephemeral")
        data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
        data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
        batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
        batch = batch_def.get_batch(batch_parameters={"dataframe": df})

        # 4 Core Expectations
        expectations = [
            gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
            gxe.ExpectColumnValuesToNotBeNull(column="paper_id"),
            gxe.ExpectColumnValuesToNotBeNull(column="title"),
            gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
            gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
            gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ]

        for exp in expectations:
            res = batch.validate(exp)
            results.append(res)
            if not res.success:
                gx_success = False

    # Freshness Check
    if total_rows > 0 and "age_days" in df.columns:
        stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
        stale_ratio = stale_rows / total_rows
    else:
        stale_rows = 0
        stale_ratio = 0.0

    freshness_passed = (stale_ratio <= 0.25) if total_rows > 0 else False
    overall_success = bool(gx_success and freshness_passed)

    report_payload: dict[str, Any] = {
        "report_name": report_name,
        "success": overall_success,
        "gx_success": bool(gx_success),
        "freshness_passed": bool(freshness_passed),
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "expectation_results": [
            {
                "expectation": getattr(r, "expectation_config", {}).type if hasattr(r, "expectation_config") else type(r).__name__,
                "success": bool(getattr(r, "success", False)),
            }
            for r in results
        ],
    }

    if report_name == "baseline":
        report_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        report_path = settings.paths.corrupted_quality_report
    else:
        report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    write_json(report_path, report_payload)
    return report_payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | None = None) -> dict[str, Any]:
    """Aggregate dataset freshness metrics and write freshness SLA report."""
    total_rows = len(df)
    if total_rows > 0 and "published" in df.columns:
        latest_published = str(df["published"].max())
        oldest_published = str(df["published"].min())
    else:
        latest_published = None
        oldest_published = None

    if total_rows > 0 and "age_days" in df.columns:
        stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
        stale_ratio = stale_rows / total_rows
    else:
        stale_rows = 0
        stale_ratio = 0.0

    is_fresh = (stale_ratio <= 0.25) if total_rows > 0 else False

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": is_fresh,
    }

    target = Path(report_path) if report_path else settings.paths.freshness_report
    write_json(target, payload)
    return payload
