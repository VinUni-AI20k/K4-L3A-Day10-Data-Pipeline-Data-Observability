from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings

logger = logging.getLogger(__name__)


def run_data_quality_checks(
    df: pd.DataFrame, settings: Settings, report_name: str
) -> dict[str, Any]:
    """Execute Great Expectations 1.x suite and return validation report."""
    logger.info(f"Running Data Quality Gate for '{report_name}' with {len(df)} records...")

    # 1. Ephemeral context (runs in RAM, no disk clutter)
    context = gx.get_context(mode="ephemeral")

    # 2. Configure DataSource, DataAsset, BatchDefinition, and Batch
    source_name = f"papers_source_{report_name}"
    asset_name = f"papers_asset_{report_name}"
    batch_name = f"papers_batch_{report_name}"
    suite_name = f"papers_suite_{report_name}"

    data_source = context.data_sources.add_pandas(name=source_name)
    data_asset = data_source.add_dataframe_asset(name=asset_name)
    batch_def = data_asset.add_batch_definition_whole_dataframe(batch_name)
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # 3. Define 4 required Expectations
    suite = gx.ExpectationSuite(name=suite_name)
    # 3.1. Row count between 5 and 5000
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    # 3.2. Columns not null
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    # 3.3. paper_id is unique
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    # 3.4. Summary length at least 30 characters
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30)
    )

    # 4. Validate
    validation_result = batch.validate(suite)
    success = bool(validation_result.success)

    # 5. Extract report dictionary
    res_dict: dict[str, Any] = (
        validation_result.to_json_dict()
        if hasattr(validation_result, "to_json_dict")
        else {"success": success}
    )
    res_dict["success"] = success
    res_dict["report_name"] = report_name
    res_dict["total_records"] = len(df)

    # 6. Save report to disk
    if report_name == "baseline":
        report_file = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        report_file = settings.paths.corrupted_quality_report
    else:
        report_file = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(res_dict, f, indent=2, ensure_ascii=False, default=str)

    logger.info(
        f"Data Quality Gate '{report_name}' completed. Status: {'PASS' if success else 'FAIL'}. Saved to {report_file}"
    )
    return res_dict


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path | str | None = None
) -> dict[str, Any]:
    """Evaluate freshness SLA: warns if records older than threshold exceed 25%."""
    total_rows = len(df)
    threshold_days = getattr(settings, "freshness_threshold_days", 180)

    if total_rows == 0:
        report = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "freshness_threshold_days": threshold_days,
            "is_fresh": True,
            "status": "EMPTY",
        }
    else:
        latest_published = (
            str(df["published"].dropna().max()) if "published" in df.columns else None
        )
        oldest_published = (
            str(df["published"].dropna().min()) if "published" in df.columns else None
        )
        stale_rows = (
            int((df["age_days"] > threshold_days).sum())
            if "age_days" in df.columns
            else 0
        )
        stale_ratio = stale_rows / total_rows
        is_fresh = bool(stale_ratio <= 0.25)

        report = {
            "latest_published": latest_published,
            "oldest_published": oldest_published,
            "stale_rows": stale_rows,
            "total_rows": total_rows,
            "stale_ratio": round(stale_ratio, 4),
            "freshness_threshold_days": threshold_days,
            "max_allowed_stale_ratio": 0.25,
            "is_fresh": is_fresh,
            "status": "PASS" if is_fresh else "STALE_WARNING",
        }

    target_path = Path(report_path) if report_path else settings.paths.freshness_report
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Freshness SLA report generated. Fresh: {report['is_fresh']} ({report['stale_rows']}/{total_rows} stale). Saved to {target_path}"
    )
    return report
