from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
from great_expectations.expectations import (
    ExpectColumnValueLengthsToBeBetween,
    ExpectColumnValuesToBeUnique,
    ExpectColumnValuesToNotBeNull,
    ExpectTableRowCountToBeBetween,
)
import pandas as pd

from core.config import Settings
from core.utils import write_json


_REQUIRED_COLUMNS = ("paper_id", "title", "text_for_embedding")
_SUMMARY_MIN_CHARS = 30
_ROW_COUNT_MIN = 5
_ROW_COUNT_MAX = 5000
_STALE_RATIO_LIMIT = 0.25


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run the GX 1.x quality gate and attach the freshness SLA result."""
    freshness = _freshness_payload(df, settings)
    expectations = _expectation_results(df)
    success = all(item["success"] for item in expectations) if expectations else False
    report = {
        "report_name": report_name,
        "success": success,
        "row_count": int(len(df)),
        "expectations": expectations,
        "freshness": freshness,
    }
    write_json(_quality_report_path(settings, report_name), report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize publication age and write the freshness SLA report."""
    payload = _freshness_payload(df, settings)
    write_json(Path(report_path), payload)
    return payload


def _expectation_results(df: pd.DataFrame) -> list[dict[str, Any]]:
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    suite = context.suites.add(
        gx.ExpectationSuite(
            name="papers_suite",
            expectations=[
                ExpectTableRowCountToBeBetween(min_value=_ROW_COUNT_MIN, max_value=_ROW_COUNT_MAX),
                *[
                    ExpectColumnValuesToNotBeNull(column=column)
                    for column in _REQUIRED_COLUMNS
                ],
                ExpectColumnValuesToBeUnique(column="paper_id"),
                ExpectColumnValueLengthsToBeBetween(column="summary", min_value=_SUMMARY_MIN_CHARS),
            ],
        )
    )
    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="papers_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    result = validation_definition.run(batch_parameters={"dataframe": df})
    parsed: list[dict[str, Any]] = []
    for item in result.results:
        config = item.expectation_config
        parsed.append(
            {
                "type": config.type,
                "success": bool(item.success),
                "kwargs": dict(config.kwargs),
            }
        )
    return parsed


def _freshness_payload(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    if "published" in df.columns:
        published = pd.to_datetime(df["published"], utc=True, errors="coerce")
    else:
        published = pd.Series(dtype="datetime64[ns, UTC]")
    if "age_days" in df.columns:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
    elif not published.empty:
        ages = (pd.Timestamp.now(tz="UTC") - published).dt.days
    else:
        ages = pd.Series(dtype="float64")

    total_rows = int(len(df))
    stale_rows = int((ages > settings.freshness_threshold_days).fillna(False).sum())
    stale_ratio = (stale_rows / total_rows) if total_rows else 1.0
    valid_dates = published.dropna()
    return {
        "latest_published": _date_text(valid_dates.max()) if not valid_dates.empty else None,
        "oldest_published": _date_text(valid_dates.min()) if not valid_dates.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": _STALE_RATIO_LIMIT,
        "is_fresh": total_rows > 0 and stale_ratio <= _STALE_RATIO_LIMIT,
    }


def _quality_report_path(settings: Settings, report_name: str) -> Path:
    named = {
        "baseline": settings.paths.baseline_quality_report,
        "corrupted": settings.paths.corrupted_quality_report,
    }
    return named.get(report_name, settings.paths.quality_dir / f"{report_name}_quality_report.json")


def _date_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    return timestamp.date().isoformat()
