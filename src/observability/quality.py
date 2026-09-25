from __future__ import annotations

from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay Data Quality Gate bang Great Expectations 1.x (ephemeral context).

    4 expectations bat buoc:
    1. So dong tu 5 den 5000.
    2. `paper_id`, `title`, `text_for_embedding` khong duoc null.
    3. `paper_id` la duy nhat.
    4. `summary` co do dai toi thieu 30 ky tu.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"{report_name}_source")
    data_asset = data_source.add_dataframe_asset(name=f"{report_name}_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"{report_name}_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    expectations = [
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="title"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
    ]

    expectation_results = []
    overall_success = True
    for expectation in expectations:
        result = batch.validate(expectation)
        overall_success = overall_success and bool(result.success)
        expectation_results.append(result.to_json_dict())

    report = {
        "report_name": report_name,
        "row_count": int(len(df)),
        "success": overall_success,
        "expectations": expectation_results,
    }

    output_path = (
        settings.paths.baseline_quality_report
        if report_name == "baseline"
        else settings.paths.corrupted_quality_report
        if report_name == "corrupted"
        else settings.paths.quality_dir / f"{report_name}_quality_report.json"
    )
    write_json(output_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop Freshness SLA: canh bao khi ty le bai bao `age_days > threshold` vuot 25%."""
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))
    stale_rows = int((df["age_days"] > threshold).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0

    payload = {
        "threshold_days": threshold,
        "latest_published": str(df["published"].max()) if total_rows else None,
        "oldest_published": str(df["published"].min()) if total_rows else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": stale_ratio <= 0.25,
    }
    write_json(report_path, payload)
    return payload
