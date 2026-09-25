from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd
from great_expectations import expectations as gxe

from core.config import Settings
from core.utils import safe_slug, write_json


MAX_STALE_RATIO = 0.25


def _freshness_payload(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    total_rows = len(df)
    published = pd.to_datetime(df.get("published"), errors="coerce", utc=True)
    if "age_days" in df:
        age_days = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        age_days = pd.Series([None] * total_rows, dtype="float64")
    stale_rows = int((age_days > settings.freshness_threshold_days).fillna(True).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    valid_dates = published.dropna() if published is not None else pd.Series(dtype="datetime64[ns, UTC]")
    return {
        "latest_published": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        "oldest_published": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": MAX_STALE_RATIO,
        "is_fresh": total_rows > 0 and stale_ratio <= MAX_STALE_RATIO,
    }


def _report_path(settings: Settings, report_name: str) -> Path:
    normalized = safe_slug(report_name)
    if normalized == "baseline":
        return settings.paths.baseline_quality_report
    if normalized == "corrupted":
        return settings.paths.corrupted_quality_report
    return settings.paths.quality_dir / f"{normalized}_quality_report.json"


def _freshness_path(settings: Settings, report_name: str) -> Path:
    normalized = safe_slug(report_name)
    if normalized == "baseline":
        return settings.paths.freshness_report
    return settings.paths.quality_dir / f"{normalized}_freshness_report.json"


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate the dataframe with the GX 1.x fluent pandas API."""
    required_columns = {"paper_id", "title", "text_for_embedding", "summary"}
    missing = sorted(required_columns - set(df.columns))
    checks: list[dict[str, Any]] = []

    if missing:
        checks.append(
            {
                "expectation": "RequiredColumnsPresent",
                "success": False,
                "details": {"missing_columns": missing},
            }
        )
    else:
        context = gx.get_context(mode="ephemeral")
        data_source = context.data_sources.add_pandas(name="papers_source")
        data_asset = data_source.add_dataframe_asset(name="papers_asset")
        batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
        batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

        expectations = [
            gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000),
            gxe.ExpectColumnValuesToNotBeNull(column="paper_id"),
            gxe.ExpectColumnValuesToNotBeNull(column="title"),
            gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"),
            gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
            gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30),
        ]
        for expectation in expectations:
            result = batch.validate(expectation, result_format="SUMMARY")
            details = dict(result.result or {})
            # Keep reports concise while retaining the useful diagnostic counts.
            details.pop("partial_unexpected_list", None)
            details.pop("partial_unexpected_counts", None)
            checks.append(
                {
                    "expectation": type(expectation).__name__,
                    "column": getattr(expectation, "column", None),
                    "success": bool(result.success),
                    "details": details,
                }
            )

    gx_success = bool(checks) and all(check["success"] for check in checks)
    freshness = build_freshness_report(df, settings, _freshness_path(settings, report_name))
    successful = sum(1 for check in checks if check["success"])
    report = {
        "report_name": report_name,
        "success": gx_success and freshness["is_fresh"],
        "gx_success": gx_success,
        "freshness_success": freshness["is_fresh"],
        "statistics": {
            "evaluated_expectations": len(checks),
            "successful_expectations": successful,
            "unsuccessful_expectations": len(checks) - successful,
            "success_percent": (100.0 * successful / len(checks)) if checks else 0.0,
        },
        "expectations": checks,
        "freshness": freshness,
    }
    write_json(_report_path(settings, report_name), report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Calculate and persist the 180-day/25%-stale freshness SLA."""
    report = _freshness_payload(df, settings)
    write_json(Path(report_path), report)
    return report
