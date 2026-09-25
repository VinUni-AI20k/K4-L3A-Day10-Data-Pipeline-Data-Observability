from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run GX 1.x expectations for data validity and freshness.

    Checks the required quality constraints and writes a JSON report to the
    quality folder so the pipeline can decide whether the data is safe to index.
    """
    if df.empty:
        payload = {
            "report_name": report_name,
            "success": False,
            "message": "DataFrame is empty.",
            "expectations": [],
            "freshness": {"is_fresh": False, "stale_rows": 0, "total_rows": 0},
        }
        output_path = (
            settings.paths.corrupted_quality_report
            if "corrupt" in report_name.lower()
            else settings.paths.baseline_quality_report
        )
        write_json(output_path, payload)
        return payload

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    validator = batch.get_validator()

    expectation_results: list[dict[str, Any]] = []

    row_count = validator.expect_table_row_count_to_be_between(min_value=5, max_value=5000)
    expectation_results.append({
        "name": "row_count_between_5_and_5000",
        "success": bool(row_count.success),
        "details": row_count.result,
    })

    for column_name in ["paper_id", "title", "text_for_embedding"]:
        result = validator.expect_column_values_to_not_be_null(column=column_name)
        expectation_results.append({
            "name": f"{column_name}_not_null",
            "success": bool(result.success),
            "details": result.result,
        })

    paper_unique = validator.expect_column_values_to_be_unique(column="paper_id")
    expectation_results.append({
        "name": "paper_id_unique",
        "success": bool(paper_unique.success),
        "details": paper_unique.result,
    })

    summary_length = validator.expect_column_value_lengths_to_be_between(
        column="summary",
        min_value=30,
        max_value=None,
    )
    expectation_results.append({
        "name": "summary_length_at_least_30",
        "success": bool(summary_length.success),
        "details": summary_length.result,
    })

    freshness_report = build_freshness_report(df, settings, settings.paths.freshness_report)
    expectation_results.append({
        "name": "freshness_threshold_check",
        "success": bool(freshness_report["is_fresh"]),
        "details": {
            "stale_rows": freshness_report["stale_rows"],
            "total_rows": freshness_report["total_rows"],
            "threshold_percent": 0.25,
        },
    })

    success = all(item["success"] for item in expectation_results)
    output_path = (
        settings.paths.corrupted_quality_report
        if "corrupt" in report_name.lower()
        else settings.paths.baseline_quality_report
    )
    payload = {
        "report_name": report_name,
        "success": success,
        "expectations": expectation_results,
        "freshness": freshness_report,
        "report_path": str(output_path),
    }
    write_json(output_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Build a freshness summary and persist it as JSON.

    Computes the newest and oldest publication dates, the number of stale rows,
    and whether the dataset remains within the acceptable freshness threshold.
    """
    total_rows = len(df)
    if total_rows == 0:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "is_fresh": False,
            "threshold_days": settings.freshness_threshold_days,
            "stale_ratio": 0.0,
        }
        write_json(Path(report_path), payload)
        return payload

    published = pd.to_datetime(df["published"], errors="coerce").dropna()
    latest_published = None if published.empty else published.max().strftime("%Y-%m-%d")
    oldest_published = None if published.empty else published.min().strftime("%Y-%m-%d")

    stale_rows = int((df.get("age_days", pd.Series([0] * total_rows, index=df.index)) > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0
    is_fresh = stale_ratio <= 0.25

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": is_fresh,
        "threshold_days": settings.freshness_threshold_days,
        "stale_ratio": stale_ratio,
    }
    write_json(Path(report_path), payload)
    return payload
