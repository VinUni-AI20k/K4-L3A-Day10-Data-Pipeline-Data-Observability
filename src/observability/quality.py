from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd
from great_expectations.expectations import (
    ExpectColumnValueLengthsToBeBetween,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectTableRowCountToBeBetween,
)

from core.config import Settings
from core.utils import safe_slug, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run the Great Expectations 1.x quality gate and persist its result.

    The context is ephemeral: validation metadata is written to the explicit
    report JSON below, while Great Expectations itself does not create project
    configuration or data-doc files.
    """

    required_columns = {"paper_id", "title", "text_for_embedding", "summary", "age_days", "published"}
    missing_columns = sorted(required_columns - set(df.columns))
    report_path = settings.paths.quality_dir / f"{safe_slug(report_name)}_quality_report.json"
    if missing_columns:
        freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
        payload = {
            "success": False,
            "report_name": report_name,
            "row_count": len(df),
            "missing_columns": missing_columns,
            "expectations": [],
            "freshness": freshness,
            "report_path": str(report_path),
        }
        write_json(report_path, payload)
        return payload

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        ("row_count", ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)),
        ("paper_id_not_null", ExpectColumnValuesToNotBeNull(column="paper_id")),
        ("title_not_null", ExpectColumnValuesToNotBeNull(column="title")),
        (
            "text_for_embedding_not_null",
            ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        ),
        ("paper_id_unique", ExpectColumnValuesToBeUnique(column="paper_id")),
        (
            "summary_length",
            ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ),
    ]
    results = []
    for name, expectation in expectations:
        result = batch.validate(expectation)
        results.append({"name": name, **result.to_json_dict()})

    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
    gx_success = all(result["success"] for result in results)
    payload = {
        "success": gx_success and freshness["is_fresh"],
        "gx_success": gx_success,
        "report_name": report_name,
        "row_count": len(df),
        "missing_columns": [],
        "expectations": results,
        "freshness": freshness,
        "report_path": str(report_path),
    }
    write_json(report_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Measure the percentage of papers beyond the configured freshness SLA."""
    target_path = Path(report_path)
    total_rows = len(df)
    published = (
        pd.to_datetime(df["published"], errors="coerce", utc=True)
        if "published" in df.columns
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    ages = (
        pd.to_numeric(df["age_days"], errors="coerce")
        if "age_days" in df.columns
        else pd.Series(index=df.index, dtype="float64")
    )
    stale_mask = ages > settings.freshness_threshold_days
    stale_rows = int(stale_mask.fillna(False).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0
    valid_dates = published.dropna()
    payload = {
        "latest_published": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        "oldest_published": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": 0.25,
        "is_fresh": bool(total_rows and stale_ratio <= 0.25),
    }
    write_json(target_path, payload)
    return payload
