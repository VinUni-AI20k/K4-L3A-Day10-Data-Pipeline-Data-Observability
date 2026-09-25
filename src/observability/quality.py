from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks bang Great Expectations 1.x va Freshness Check.

    1. Khoi tao Ephemeral context cua GX 1.x.
    2. Thiet lap 4 Expectations bat buoc:
       - ExpectTableRowCountToBeBetween (5 den 5000)
       - ExpectColumnValuesToNotBeNull (paper_id, title, text_for_embedding)
       - ExpectColumnValuesToBeUnique (paper_id)
       - ExpectColumnValueLengthsToBeBetween (summary >= 30 ky tu)
    3. Thuc hien Freshness Check voi nguong stale <= 25%.
    4. Ghi ket qua vao data/quality/ va tra ve ket qua.
    """
    # 1. Ephemeral Context & Data Asset Setup
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # 2. Configure Expectation Suite
    suite = gx.ExpectationSuite(name=f"papers_suite_{report_name}")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    # Validate batch against expectation suite
    gx_result = batch.validate(suite)

    # 3. Freshness Check
    if report_name == "baseline":
        freshness_report_path = settings.paths.freshness_report
    else:
        freshness_report_path = settings.paths.quality_dir / f"{report_name}_freshness_report.json"

    freshness = build_freshness_report(df, settings, freshness_report_path)

    # 4. Overall result & Report payload
    overall_success = bool(gx_result.success and freshness.get("is_fresh", False))

    expectations_summary: list[dict[str, Any]] = []
    for r in gx_result.results:
        exp_type = r.expectation_config.type if hasattr(r, "expectation_config") else str(type(r))
        kwargs = getattr(r.expectation_config, "kwargs", {}) if hasattr(r, "expectation_config") else {}
        expectations_summary.append(
            {
                "expectation_type": exp_type,
                "success": bool(r.success),
                "kwargs": kwargs,
            }
        )

    report_payload: dict[str, Any] = {
        "report_name": report_name,
        "success": overall_success,
        "gx_success": bool(gx_result.success),
        "freshness_success": bool(freshness.get("is_fresh", False)),
        "row_count": len(df),
        "expectations": expectations_summary,
        "freshness": freshness,
    }

    # Determine report output path
    if report_name == "baseline":
        report_file = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        report_file = settings.paths.corrupted_quality_report
    else:
        report_file = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    write_json(report_file, report_payload)
    return report_payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | str | None) -> dict[str, Any]:
    """Tong hop freshness report theo SLA (ty le age_days > 180 khong vuot qua 25%)."""
    total_rows = len(df)
    threshold_days = settings.freshness_threshold_days

    if df.empty:
        payload = {
            "latest_published": "",
            "oldest_published": "",
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "threshold_days": threshold_days,
            "max_stale_ratio": 0.25,
            "is_fresh": True,
        }
        if report_path:
            write_json(Path(report_path), payload)
        return payload

    latest_published = str(df["published"].max()) if "published" in df.columns else ""
    oldest_published = str(df["published"].min()) if "published" in df.columns else ""

    if "age_days" in df.columns:
        stale_rows = int((df["age_days"] > threshold_days).sum())
    else:
        now = now_utc()
        pub_dates = pd.to_datetime(df["published"], utc=True, errors="coerce")
        age_days_series = (now - pub_dates).dt.days
        stale_rows = int((age_days_series > threshold_days).sum())

    stale_ratio = float(stale_rows / total_rows) if total_rows > 0 else 0.0
    is_fresh = bool(stale_ratio <= 0.25)

    payload = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "threshold_days": threshold_days,
        "max_stale_ratio": 0.25,
        "is_fresh": is_fresh,
    }

    if report_path:
        write_json(Path(report_path), payload)

    return payload
