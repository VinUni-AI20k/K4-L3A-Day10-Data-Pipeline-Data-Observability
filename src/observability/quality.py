from __future__ import annotations

from pathlib import Path
from typing import Any

import great_expectations as gx
from great_expectations import expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, safe_slug, write_json

MIN_ROW_COUNT = 5
MAX_ROW_COUNT = 5000
MIN_SUMMARY_CHARS = 30
MAX_SUMMARY_CHARS = 20000
NOT_NULL_COLUMNS = ["paper_id", "title", "text_for_embedding"]
STALE_RATIO_THRESHOLD = 0.25


def _build_expectation_suite() -> gx.ExpectationSuite:
    """4 hang rao kiem dinh bat buoc theo chuan Great Expectations 1.x."""
    suite = gx.ExpectationSuite(name="papers_quality_suite")

    # 1. So luong ban ghi nam trong nguong hop le.
    suite.add_expectation(
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROW_COUNT, max_value=MAX_ROW_COUNT)
    )
    # 2. Cac cot trong yeu khong duoc null.
    for column in NOT_NULL_COLUMNS:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))
    # 3. paper_id phai duy nhat (chan duplicate index).
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    # 4. summary phai du dai de AI doc hieu.
    suite.add_expectation(
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="summary", min_value=MIN_SUMMARY_CHARS, max_value=MAX_SUMMARY_CHARS
        )
    )
    return suite


def _resolve_report_path(settings: Settings, report_name: str) -> Path:
    if report_name == "baseline":
        return settings.paths.baseline_quality_report
    if report_name == "corrupted":
        return settings.paths.corrupted_quality_report
    return settings.paths.quality_dir / f"{safe_slug(report_name)}_quality_report.json"


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Data Quality Gate dung cu phap Great Expectations 1.x.

    Tra ve dict gom `success` (ket qua GX), chi tiet tung expectation va
    phan freshness de cac buoc phia sau bao cao lai.
    """
    settings.paths.gx_dir.mkdir(parents=True, exist_ok=True)

    # --- Chuan GX 1.x: ephemeral context -> pandas data source -> batch definition ---
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    suite = _build_expectation_suite()
    validation_result = batch.validate(suite)
    result_dict = validation_result.to_json_dict()

    expectation_results: list[dict[str, Any]] = []
    for item in result_dict.get("results", []):
        config = item.get("expectation_config", {}) or {}
        kwargs = config.get("kwargs", {}) or {}
        expectation_results.append(
            {
                "expectation": config.get("type") or config.get("expectation_type", "unknown"),
                "column": kwargs.get("column"),
                "success": bool(item.get("success")),
                "observed_value": (item.get("result", {}) or {}).get("observed_value"),
                "unexpected_count": (item.get("result", {}) or {}).get("unexpected_count"),
            }
        )

    freshness = summarize_freshness(df, settings)
    statistics = result_dict.get("statistics", {}) or {}

    payload: dict[str, Any] = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "gx_version": gx.__version__,
        "row_count": int(len(df)),
        "success": bool(validation_result.success),
        "gate_passed": bool(validation_result.success) and bool(freshness["is_fresh"]),
        "evaluated_expectations": statistics.get("evaluated_expectations"),
        "successful_expectations": statistics.get("successful_expectations"),
        "unsuccessful_expectations": statistics.get("unsuccessful_expectations"),
        "failed_expectations": [item for item in expectation_results if not item["success"]],
        "expectations": expectation_results,
        "freshness": freshness,
    }

    write_json(_resolve_report_path(settings, report_name), payload)
    return payload


def summarize_freshness(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    """Do do tuoi du lieu: bao nhieu % ban ghi da qua han SLA."""
    total_rows = int(len(df))
    threshold = settings.freshness_threshold_days

    if total_rows == 0:
        return {
            "threshold_days": threshold,
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 1.0,
            "max_age_days": None,
            "is_fresh": False,
        }

    published = df["published"].astype(str)
    published = published[published.str.len() > 0]
    ages = pd.to_numeric(df["age_days"], errors="coerce").fillna(-1)
    stale_rows = int((ages > threshold).sum())
    stale_ratio = stale_rows / total_rows

    return {
        "threshold_days": threshold,
        "latest_published": published.max() if not published.empty else None,
        "oldest_published": published.min() if not published.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "max_age_days": int(ages.max()) if total_rows else None,
        "is_fresh": bool(stale_ratio <= STALE_RATIO_THRESHOLD),
    }


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report va ghi ra JSON."""
    payload = summarize_freshness(df, settings)
    payload["generated_at"] = now_utc().isoformat()
    payload["stale_ratio_threshold"] = STALE_RATIO_THRESHOLD
    payload["alert"] = (
        "OK - du lieu con tuoi."
        if payload["is_fresh"]
        else f"CANH BAO - {payload['stale_rows']}/{payload['total_rows']} ban ghi qua han {settings.freshness_threshold_days} ngay."
    )
    write_json(Path(report_path), payload)
    return payload
