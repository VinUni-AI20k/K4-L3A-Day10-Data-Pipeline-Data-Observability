from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Thuc hien kiem dinh chat luong du lieu bang Great Expectations 1.x ephemeral mode."""
    context = gx.get_context(mode="ephemeral")
    unique_suffix = f"{safe_slug(report_name)}_{uuid4().hex[:6]}"

    data_source = context.data_sources.add_pandas(name=f"papers_source_{unique_suffix}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{unique_suffix}")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{unique_suffix}")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_suite_{unique_suffix}"))

    # 4 Expectations thiet yeu
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    validation_result = batch.validate(suite)

    expectation_results = []
    for r in validation_result.results:
        exp_config = getattr(r, "expectation_config", None)
        exp_type = getattr(exp_config, "type", str(type(exp_config).__name__)) if exp_config else "unknown"
        expectation_results.append(
            {
                "expectation_type": exp_type,
                "success": bool(r.success),
                "result": getattr(r, "result", {}),
            }
        )

    summary = {
        "report_name": report_name,
        "success": bool(validation_result.success),
        "total_expectations": len(validation_result.results),
        "successful_expectations": sum(1 for r in validation_result.results if r.success),
        "failed_expectations": sum(1 for r in validation_result.results if not r.success),
        "evaluated_rows": len(df),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "expectation_results": expectation_results,
    }

    # Xac dinh duong dan luu
    if report_name == "baseline":
        out_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        out_path = settings.paths.corrupted_quality_report
    else:
        out_path = settings.paths.quality_dir / f"{safe_slug(report_name)}_quality_report.json"

    write_json(out_path, summary)
    return summary


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | None = None) -> dict[str, Any]:
    """Tong hop va danh gia Freshness SLA theo nguong age_days."""
    total_rows = len(df)
    stale_rows = 0
    stale_ratio = 0.0

    if not df.empty and "age_days" in df.columns:
        stale_rows = int((df["age_days"] > settings.freshness_threshold_days).sum())
        stale_ratio = stale_rows / total_rows if total_rows > 0 else 0.0

    latest_published = str(df["published"].max()) if not df.empty and "published" in df.columns else ""
    oldest_published = str(df["published"].min()) if not df.empty and "published" in df.columns else ""

    # Freshness SLA: Canh bao is_fresh = False neu ty le stale > 25%
    is_fresh = stale_ratio <= 0.25

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "is_fresh": is_fresh,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    target_path = report_path or settings.paths.freshness_report
    write_json(target_path, payload)
    return payload

