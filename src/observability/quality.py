from __future__ import annotations

from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run Great Expectations 1.x checks and persist a compact quality report."""
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"{report_name}_papers_suite")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    for column in ["paper_id", "title", "text_for_embedding"]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30, mostly=0.95))

    validation = batch.validate(suite)
    validation_payload = validation.to_json_dict()
    freshness = _freshness_summary(df, settings)
    success = bool(validation.success and freshness["is_fresh"])

    payload = {
        "report_name": report_name,
        "success": success,
        "gx_success": bool(validation.success),
        "freshness_success": freshness["is_fresh"],
        "row_count": int(len(df)),
        "freshness": freshness,
        "expectations": [
            {
                "expectation_type": result["expectation_config"]["type"],
                "success": bool(result["success"]),
                "observed_value": result.get("result", {}).get("observed_value"),
                "unexpected_count": result.get("result", {}).get("unexpected_count"),
            }
            for result in validation_payload.get("results", [])
        ],
        "statistics": validation_payload.get("statistics", {}),
    }

    report_path = _quality_report_path(settings, report_name)
    write_json(report_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Build and persist a freshness SLA report."""
    payload = _freshness_summary(df, settings)
    write_json(report_path, payload)
    return payload


def _quality_report_path(settings: Settings, report_name: str):
    lowered = report_name.lower()
    if "corrupt" in lowered:
        return settings.paths.corrupted_quality_report
    if "baseline" in lowered:
        return settings.paths.baseline_quality_report
    return settings.paths.quality_dir / f"{report_name}_quality_report.json"


def _freshness_summary(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    total_rows = int(len(df))
    if total_rows == 0 or "published" not in df.columns:
        return {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": total_rows,
            "stale_ratio": 0.0,
            "threshold_days": settings.freshness_threshold_days,
            "max_stale_ratio": 0.25,
            "is_fresh": False,
        }

    published = pd.to_datetime(df["published"], utc=True, errors="coerce")
    age_days = pd.to_numeric(df.get("age_days", pd.Series(dtype=float)), errors="coerce")
    stale_rows = int((age_days > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0
    valid_published = published.dropna()

    return {
        "latest_published": valid_published.max().date().isoformat() if not valid_published.empty else None,
        "oldest_published": valid_published.min().date().isoformat() if not valid_published.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": 0.25,
        "is_fresh": stale_ratio <= 0.25,
    }
