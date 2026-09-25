from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run GX 1.x data quality checks on the cleaned DataFrame.

    Expectations:
      - ExpectTableRowCountToBeBetween: 5–5000 rows
      - ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding
      - ExpectColumnValuesToBeUnique: paper_id
      - ExpectColumnValueLengthsToBeBetween: summary >= 30 chars
    """
    import great_expectations as gx

    results: dict[str, Any] = {
        "report_name": report_name,
        "run_timestamp": datetime.utcnow().isoformat(),
        "total_rows": int(len(df)),
        "expectations": [],
        "passed": True,
    }

    # GX 1.x ephemeral context
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"{report_name}_batch")

    # Build expectation suite
    suite = context.suites.add(gx.ExpectationSuite(name=f"{report_name}_suite"))
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)
    )
    for col in ("paper_id", "title", "text_for_embedding"):
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(column=col)
        )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30)
    )

    # Run validation
    validation = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch_def, suite=suite, name=f"{report_name}_validation")
    )
    validation_result = validation.run(batch_parameters={"dataframe": df})

    # Extract per-expectation results
    for res in validation_result.results:
        exp_type = res.expectation_config.type
        exp_results = {
            "expectation": exp_type,
            "success": res.success,
            "result": res.result,
        }
        results["expectations"].append(exp_results)
        if not res.success:
            results["passed"] = False

    results["success"] = results["passed"]

    # Persist report
    settings.paths.quality_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.paths.quality_dir / f"{report_name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    results["report_path"] = str(out_path)

    return results


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path
) -> dict[str, Any]:
    """Build freshness report: check stale papers (age_days > 180).

    Stale threshold configurable via settings.freshness_threshold_days.
    """
    threshold = settings.freshness_threshold_days
    total = len(df)
    stale_rows = int((df["age_days"] > threshold).sum())
    stale_ratio = round(stale_rows / total, 4) if total > 0 else 0.0
    is_fresh = stale_ratio <= 0.25

    report: dict[str, Any] = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "total_rows": total,
        "stale_rows": stale_rows,
        "stale_ratio_pct": round(stale_ratio * 100, 2),
        "threshold_days": threshold,
        "is_fresh": is_fresh,
    }

    if "published_date" in df.columns and df["published_date"].notna().any():
        report["latest_published"] = (
            df["published_date"].max().isoformat() if hasattr(df["published_date"].max(), "isoformat") else str(df["published_date"].max())
        )
        report["oldest_published"] = (
            df["published_date"].min().isoformat() if hasattr(df["published_date"].min(), "isoformat") else str(df["published_date"].min())
        )

    if not is_fresh:
        report["warning"] = (
            f"Stale ratio {report['stale_ratio_pct']}% exceeds 25% threshold. "
            "Consider fetching newer papers."
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report
