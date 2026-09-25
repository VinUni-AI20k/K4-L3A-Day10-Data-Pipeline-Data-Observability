from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks dung Great Expectations 1.x (ephemeral context) va Freshness SLA.

    Bao gom cac expectations:
    1. ExpectTableRowCountToBeBetween (5 - 5000 rows).
    2. ExpectColumnValuesToNotBeNull (paper_id).
    3. ExpectColumnValuesToBeUnique (paper_id).
    4. ExpectColumnValuesToNotBeNull (title).
    5. ExpectColumnValuesToNotBeNull (text_for_embedding).
    6. ExpectColumnValueLengthsToBeBetween (summary >= 30 chars).
    7. Freshness check voi age_days.

    Ghi ket qua vao data/quality/<report_name>_quality_report.json.
    """
    freshness_path = settings.paths.freshness_report if report_name == "baseline" else None
    freshness = build_freshness_report(df, settings, freshness_path)

    context = gx.get_context(mode="ephemeral")
    source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
    asset = source.add_dataframe_asset(name=f"papers_asset_{report_name}")
    batch_def = asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"papers_suite_{report_name}")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    val_result = batch.validate(suite)
    gx_success = bool(val_result.success)

    expectations = [
        {
            "expectation": res.expectation_config.type,
            "kwargs": dict(res.expectation_config.kwargs),
            "success": bool(res.success),
        }
        for res in val_result.results
    ]

    success = bool(gx_success and freshness["is_fresh"])

    report = {
        "report_name": report_name,
        "success": success,
        "gx_success": gx_success,
        "total_records": len(df),
        "freshness": freshness,
        "expectations": expectations,
        "evaluated_at": now_utc().isoformat(),
    }

    report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"
    write_json(report_path, report)

    return report


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path | str | None = None
) -> dict[str, Any]:
    """Tong hop freshness report dua tren age_days va freshness_threshold_days.

    Canh bao is_fresh = False neu ty le stale_rows (age_days > threshold) > 25%.
    """
    threshold = settings.freshness_threshold_days
    total_rows = len(df)

    if total_rows == 0:
        latest = ""
        oldest = ""
        stale_rows = 0
        stale_ratio = 0.0
        is_fresh = True
    else:
        latest = str(df["published"].max()) if "published" in df.columns else ""
        oldest = str(df["published"].min()) if "published" in df.columns else ""
        stale_rows = int((df["age_days"] > threshold).sum()) if "age_days" in df.columns else 0
        stale_ratio = float(stale_rows / total_rows)
        is_fresh = bool(stale_ratio <= 0.25)

    report = {
        "latest_published": latest,
        "oldest_published": oldest,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "freshness_threshold_days": threshold,
        "is_fresh": is_fresh,
    }

    if report_path is not None:
        write_json(Path(report_path), report)

    return report
