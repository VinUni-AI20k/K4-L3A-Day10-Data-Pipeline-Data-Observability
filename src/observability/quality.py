from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json
import great_expectations as gx


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """TODO(student): tao bo data quality checks.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    required = ["paper_id", "title", "summary", "text_for_embedding"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        result = {"success": False, "missing_columns": missing, "results": []}
    else:
        context = gx.get_context(mode="ephemeral")
        source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
        asset = source.add_dataframe_asset(name=f"papers_asset_{report_name}")
        definition = asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
        batch = definition.get_batch(batch_parameters={"dataframe": df})
        suite = gx.ExpectationSuite(name=f"papers_quality_{report_name}")
        suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
        for column in ("paper_id", "title", "text_for_embedding"):
            suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=column))
        suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
        suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))
        result = batch.validate(suite).to_json_dict()
        result["missing_columns"] = []
    result["report_name"] = report_name
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """TODO(student): tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    ages = pd.to_numeric(df.get("age_days", pd.Series(dtype=float)), errors="coerce")
    dates = pd.to_datetime(df.get("published", pd.Series(dtype=object)), errors="coerce", utc=True)
    total = len(df)
    stale = int((ages > settings.freshness_threshold_days).sum())
    ratio = stale / total if total else 1.0
    result = {
        "latest_published": dates.max().isoformat() if dates.notna().any() else None,
        "oldest_published": dates.min().isoformat() if dates.notna().any() else None,
        "stale_rows": stale, "total_rows": total, "stale_ratio": ratio,
        "is_fresh": bool(total and ratio <= 0.25),
    }
    write_json(report_path, result)
    return result
