from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("GX_ANALYTICS_ENABLED", "False")

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROWS = 5
MAX_ROWS = 5000
MIN_SUMMARY_CHARS = 30
MIN_TITLE_CHARS = 20
NOT_NULL_COLUMNS = ("paper_id", "title", "summary", "text_for_embedding")
# Freshness SLA: data is stale when more than 25% of papers are older than the threshold.
MAX_STALE_RATIO = 0.25


def _build_expectations() -> list[gxe.Expectation]:
    expectations: list[gxe.Expectation] = [
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS),
    ]
    expectations += [gxe.ExpectColumnValuesToNotBeNull(column=column) for column in NOT_NULL_COLUMNS]
    expectations += [
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
        gxe.ExpectColumnValueLengthsToBeBetween(column="title", min_value=MIN_TITLE_CHARS),
    ]
    return expectations


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    config = result["expectation_config"]
    kwargs = {key: value for key, value in config["kwargs"].items() if key != "batch_id"}
    details = result.get("result") or {}
    summary = {
        "expectation": config["type"],
        "kwargs": kwargs,
        "success": result["success"],
    }
    for key in ("observed_value", "element_count", "unexpected_count", "unexpected_percent", "partial_unexpected_list"):
        if key in details:
            summary[key] = details[key]
    exception = result.get("exception_info") or {}
    if exception.get("raised_exception"):
        summary["exception"] = exception.get("exception_message")
    return summary


def _age_days(df: pd.DataFrame) -> pd.Series:
    if "age_days" in df.columns:
        return pd.to_numeric(df["age_days"], errors="coerce")
    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    return (pd.Timestamp(now_utc()) - published).dt.days


def _freshness_payload(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    total_rows = int(len(df))
    ages = _age_days(df) if total_rows else pd.Series(dtype=float)
    published = pd.to_datetime(df["published"], errors="coerce", utc=True) if "published" in df.columns else pd.Series(dtype="datetime64[ns, UTC]")
    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    return {
        "checked_at": now_utc().isoformat(),
        "latest_published": published.max().date().isoformat() if published.notna().any() else None,
        "oldest_published": published.min().date().isoformat() if published.notna().any() else None,
        "min_age_days": int(ages.min()) if ages.notna().any() else None,
        "max_age_days": int(ages.max()) if ages.notna().any() else None,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": MAX_STALE_RATIO,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": total_rows > 0 and stale_ratio <= MAX_STALE_RATIO,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate a cleaned dataframe with a Great Expectations 1.x suite plus a freshness SLA check.

    `success` reflects the GX quality gate only; freshness is reported alongside as a
    non-blocking alert so stale-but-valid data does not stop the pipeline.
    Writes `data/quality/<report_name>_quality_report.json` and the raw GX result to `data/quality/gx/`.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_quality_{report_name}"))
    for expectation in _build_expectations():
        suite.add_expectation(expectation)

    validation = batch.validate(suite).to_json_dict()
    checks = [_summarize_result(result) for result in validation["results"]]
    failed = [check for check in checks if not check["success"]]
    freshness = _freshness_payload(df, settings)

    report = {
        "report_name": report_name,
        "checked_at": now_utc().isoformat(),
        "gx_version": gx.__version__,
        "row_count": int(len(df)),
        "success": bool(validation["success"]),
        "evaluated_expectations": len(checks),
        "successful_expectations": len(checks) - len(failed),
        "failed_expectations": [f"{check['expectation']}({check['kwargs'].get('column', 'table')})" for check in failed],
        "checks": checks,
        "freshness": freshness,
        "alerts": [f"GX check failed: {check['expectation']} {check['kwargs']}" for check in failed],
    }
    if not freshness["is_fresh"]:
        report["alerts"].append(
            f"Freshness SLA breached: {freshness['stale_rows']}/{freshness['total_rows']} rows older than "
            f"{settings.freshness_threshold_days} days (ratio {freshness['stale_ratio']:.0%} > {MAX_STALE_RATIO:.0%})."
        )

    write_json(settings.paths.gx_dir / f"{report_name}_validation.json", validation)
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize dataset freshness (latest/oldest published, stale rows, `is_fresh`) and write it as JSON."""
    payload = _freshness_payload(df, settings)
    write_json(Path(report_path), payload)
    return payload
