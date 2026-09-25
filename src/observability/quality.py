from __future__ import annotations

from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json

def run_data_quality_checks(
    df: pd.DataFrame,
    settings: Settings,
    report_name: str,
) -> dict[str, Any]:

    context = gx.get_context(mode="ephemeral")

    data_source = context.data_sources.add_pandas(
        name=f"papers_source_{report_name}"
    )

    data_asset = data_source.add_dataframe_asset(
        name=f"papers_asset_{report_name}"
    )

    batch_definition = (
        data_asset.add_batch_definition_whole_dataframe(
            f"papers_batch_{report_name}"
        )
    )

    batch = batch_definition.get_batch(
        batch_parameters={
            "dataframe": df
        }
    )

    expectations = [
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=5,
            max_value=5000,
        ),

        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="paper_id"
        ),

        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="title"
        ),

        gx.expectations.ExpectColumnValuesToNotBeNull(
            column="text_for_embedding"
        ),

        gx.expectations.ExpectColumnValuesToBeUnique(
            column="paper_id"
        ),

        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="summary",
            min_value=30,
        ),
    ]

    results = []

    for expectation in expectations:
        validation_result = batch.validate(expectation)

        results.append(
            {
                "expectation": expectation.__class__.__name__,
                "success": bool(validation_result.success),
            }
        )

    success = all(
        result["success"]
        for result in results
    )

    payload = {
        "report_name": report_name,
        "success": success,
        "row_count": len(df),
        "checks": results,
    }

    if "corrupt" in report_name.lower():
        output_path = settings.paths.corrupted_quality_report
    else:
        output_path = settings.paths.baseline_quality_report

    write_json(output_path, payload)

    return payload


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path,
) -> dict[str, Any]:

    if df.empty:
        payload = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "is_fresh": False,
        }

        write_json(report_path, payload)

        return payload

    published = pd.to_datetime(
        df["published"],
        errors="coerce",
        utc=True,
    )

    stale_mask = (
        df["age_days"]
        > settings.freshness_threshold_days
    )

    stale_rows = int(stale_mask.sum())
    total_rows = len(df)

    stale_ratio = (
        stale_rows / total_rows
        if total_rows
        else 0.0
    )

    payload = {
        "latest_published": (
            published.max().strftime("%Y-%m-%d")
            if published.notna().any()
            else None
        ),
        "oldest_published": (
            published.min().strftime("%Y-%m-%d")
            if published.notna().any()
            else None
        ),
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": stale_ratio,
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": stale_ratio <= 0.25,
    }

    write_json(report_path, payload)

    return payload
