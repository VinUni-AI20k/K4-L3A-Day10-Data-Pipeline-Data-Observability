from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


STALE_RATIO_LIMIT = 0.25


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    """Resolve well-known report names while still supporting ad-hoc checks."""
    normalized = report_name.strip().lower().removesuffix(".json")
    if "corrupt" in normalized:
        return settings.paths.corrupted_quality_report
    if "baseline" in normalized:
        return settings.paths.baseline_quality_report
    if "repair" in normalized:
        return settings.paths.quality_dir / "repaired_quality_report.json"
    return settings.paths.quality_dir / f"{normalized or 'quality_report'}.json"


def _result_payload(name: str, result: Any) -> dict[str, Any]:
    """Convert a GX validation result into a compact JSON-safe record."""
    raw = result.to_json_dict()
    result_detail = raw.get("result", {})
    exception_info = raw.get("exception_info", {})
    return {
        "name": name,
        "success": bool(raw.get("success", False)),
        "observed_value": result_detail.get("observed_value"),
        "element_count": result_detail.get("element_count"),
        "unexpected_count": result_detail.get("unexpected_count"),
        "unexpected_percent": result_detail.get("unexpected_percent"),
        "exception": exception_info.get("exception_message"),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run the required Great Expectations 1.x gate and persist its report."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    expectations: list[tuple[str, Any]] = [
        (
            "row_count_between_5_and_5000",
            gx.expectations.ExpectTableRowCountToBeBetween(
                min_value=5,
                max_value=5000,
                catch_exceptions=True,
                result_format="SUMMARY",
            ),
        ),
        *[
            (
                f"{column}_not_null",
                gx.expectations.ExpectColumnValuesToNotBeNull(
                    column=column,
                    catch_exceptions=True,
                    result_format="SUMMARY",
                ),
            )
            for column in ("paper_id", "title", "text_for_embedding")
        ],
        (
            "paper_id_unique",
            gx.expectations.ExpectColumnValuesToBeUnique(
                column="paper_id",
                catch_exceptions=True,
                result_format="SUMMARY",
            ),
        ),
        (
            "summary_min_length_30",
            gx.expectations.ExpectColumnValueLengthsToBeBetween(
                column="summary",
                min_value=30,
                catch_exceptions=True,
                result_format="SUMMARY",
            ),
        ),
    ]

    checks = [_result_payload(name, batch.validate(expectation)) for name, expectation in expectations]
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
    gx_success = all(check["success"] for check in checks)

    payload: dict[str, Any] = {
        "report_name": report_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "success": gx_success and freshness["is_fresh"],
        "gx_success": gx_success,
        "freshness_success": freshness["is_fresh"],
        "total_rows": int(len(df)),
        "statistics": {
            "evaluated_expectations": len(checks),
            "successful_expectations": sum(check["success"] for check in checks),
            "unsuccessful_expectations": sum(not check["success"] for check in checks),
            "success_percent": round(
                100.0 * sum(check["success"] for check in checks) / len(checks), 2
            ),
        },
        "checks": checks,
        "freshness": freshness,
    }
    write_json(_quality_report_path(settings, report_name), payload)
    return payload


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: str | Path
) -> dict[str, Any]:
    """Measure the share of papers older than the configured freshness SLA."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    total_rows = int(len(df))
    published = pd.to_datetime(
        df.get("published", pd.Series(index=df.index, dtype="object")),
        errors="coerce",
        utc=True,
    )

    if "age_days" in df.columns:
        age_days = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        now = pd.Timestamp.now(tz="UTC")
        age_days = (now - published).dt.total_seconds() / 86_400

    stale_mask = age_days > settings.freshness_threshold_days
    stale_rows = int(stale_mask.fillna(False).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    valid_dates = published.dropna()

    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "stale_ratio_limit": STALE_RATIO_LIMIT,
        "latest_published": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        "oldest_published": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
        "stale_rows": stale_rows,
        "invalid_or_missing_dates": int(published.isna().sum()),
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "stale_percent": round(stale_ratio * 100, 2),
        "is_fresh": bool(total_rows > 0 and stale_ratio <= STALE_RATIO_LIMIT),
    }
    write_json(Path(report_path), payload)
    return payload
