from __future__ import annotations

from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name="papers_suite"))
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    validation_def = context.validation_definitions.add(
        gx.ValidationDefinition(name="papers_validation", data=batch_def, suite=suite)
    )
    result = validation_def.run(batch_parameters={"dataframe": df})

    results_list = []
    for r in result.results:
        cfg = r.expectation_config
        exp_type = getattr(cfg, "type", None) or getattr(cfg, "expectation_type", str(cfg))
        kwargs = getattr(cfg, "kwargs", {})
        results_list.append({
            "expectation": exp_type,
            "success": bool(r.success),
            "kwargs": dict(kwargs) if kwargs else {},
        })

    stats = result.statistics if isinstance(result.statistics, dict) else {}
    report = {
        "report_name": report_name,
        "success": bool(result.success),
        "statistics": {
            "evaluated": stats.get("evaluated_expectations", len(results_list)),
            "successful": stats.get("successful_expectations", sum(1 for r in results_list if r["success"])),
        },
        "results": results_list,
    }

    out_path = settings.paths.quality_dir / f"{report_name}.json"
    write_json(out_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    threshold = settings.freshness_threshold_days
    total = len(df)
    stale = int((df["age_days"] > threshold).sum()) if "age_days" in df.columns else 0
    stale_ratio = stale / total if total > 0 else 0.0
    is_fresh = stale_ratio <= 0.25

    report = {
        "threshold_days": threshold,
        "total_rows": total,
        "stale_rows": stale,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": is_fresh,
        "latest_published": df["published"].max() if "published" in df.columns else None,
        "oldest_published": df["published"].min() if "published" in df.columns else None,
    }
    write_json(report_path, report)
    return report
