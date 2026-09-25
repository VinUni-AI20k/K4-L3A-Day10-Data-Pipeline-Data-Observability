from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


_MIN_ROWS = 5
_MAX_ROWS = 5_000
_MIN_SUMMARY_LENGTH = 30
_MAX_STALE_RATIO = 0.25
_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "text_for_embedding",
    "published",
    "age_days",
}


def _prepare_for_validation(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy whose missing schema/blank values fail GX expectations."""
    prepared = df.copy()
    for column in _REQUIRED_COLUMNS:
        if column not in prepared.columns:
            prepared[column] = "" if column == "summary" else pd.NA

    for column in ("paper_id", "title", "text_for_embedding"):
        blank = prepared[column].astype("string").str.strip().eq("")
        prepared.loc[blank, column] = pd.NA

    # GX length expectations ignore nulls by default. Converting missing summaries
    # to an empty string ensures missing content fails the minimum length check.
    prepared["summary"] = prepared["summary"].fillna("").astype(str)
    return prepared


def _validation_payload(name: str, result: Any) -> dict[str, Any]:
    serialized = result.to_json_dict()
    expectation_config = serialized.get("expectation_config", {})
    return {
        "name": name,
        "type": expectation_config.get("type"),
        "success": bool(result.success),
        "kwargs": expectation_config.get("kwargs", {}),
        "result": serialized.get("result", {}),
        "exception_info": serialized.get("exception_info", {}),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run the required Great Expectations 1.x checks and freshness gate.

    The function uses an ephemeral GX context, so validation does not generate a
    Great Expectations project or other temporary configuration files.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    prepared = _prepare_for_validation(df)
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": prepared})

    expectations = [
        (
            "row_count_between_5_and_5000",
            gx.expectations.ExpectTableRowCountToBeBetween(
                min_value=_MIN_ROWS,
                max_value=_MAX_ROWS,
            ),
        ),
        *[
            (
                f"{column}_not_null",
                gx.expectations.ExpectColumnValuesToNotBeNull(column=column),
            )
            for column in ("paper_id", "title", "text_for_embedding")
        ],
        (
            "paper_id_unique",
            gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        ),
        (
            "summary_length_at_least_30",
            gx.expectations.ExpectColumnValueLengthsToBeBetween(
                column="summary",
                min_value=_MIN_SUMMARY_LENGTH,
            ),
        ),
    ]

    validation_results = [
        _validation_payload(name, batch.validate(expectation))
        for name, expectation in expectations
    ]
    successful_expectations = sum(result["success"] for result in validation_results)
    gx_success = successful_expectations == len(validation_results)

    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
    report_path = settings.paths.quality_dir / f"{safe_slug(report_name)}_quality_report.json"
    payload = {
        "report_name": report_name,
        "success": gx_success and freshness["is_fresh"],
        "gx_success": gx_success,
        "freshness_success": freshness["is_fresh"],
        "evaluated_rows": len(df),
        "statistics": {
            "evaluated_expectations": len(validation_results),
            "successful_expectations": successful_expectations,
            "unsuccessful_expectations": len(validation_results) - successful_expectations,
        },
        "expectations": validation_results,
        "freshness": freshness,
        "report_path": str(report_path),
    }
    write_json(report_path, payload)
    return payload


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path: str | Path,
) -> dict[str, Any]:
    """Evaluate the freshness SLA and write its JSON report.

    Data passes when at most 25% of rows are older than the configured freshness
    threshold (180 days by default). Missing or invalid ages make the freshness
    result fail because the dataset cannot be assessed reliably.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    total_rows = len(df)
    if "age_days" in df.columns:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        ages = pd.Series(pd.NA, index=df.index, dtype="Float64")

    invalid_age_rows = int(ages.isna().sum())
    stale_mask = ages.gt(settings.freshness_threshold_days).fillna(False)
    stale_rows = int(stale_mask.sum())
    stale_ratio = stale_rows / total_rows if total_rows else 0.0

    if "published" in df.columns:
        published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    else:
        published = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    valid_published = published.dropna()
    latest_published = (
        valid_published.max().date().isoformat() if not valid_published.empty else None
    )
    oldest_published = (
        valid_published.min().date().isoformat() if not valid_published.empty else None
    )

    is_fresh = (
        total_rows > 0
        and invalid_age_rows == 0
        and stale_ratio <= _MAX_STALE_RATIO
    )
    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "maximum_stale_ratio": _MAX_STALE_RATIO,
        "stale_rows": stale_rows,
        "invalid_age_rows": invalid_age_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "is_fresh": is_fresh,
    }
    write_json(Path(report_path), payload)
    return payload
