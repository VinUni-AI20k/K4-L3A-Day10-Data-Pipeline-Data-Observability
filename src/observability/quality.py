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


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path: Path | None = None
) -> dict[str, Any]:
    """Tổng hợp & kiểm tra Freshness SLA cho DataFrame bài báo.

    Cảnh báo nếu tỷ lệ bài báo cũ (age_days > threshold_days, mặc định 180) vượt quá 25%.
    """
    threshold_days = getattr(settings, "freshness_threshold_days", 180)
    total_rows = len(df)

    if total_rows == 0 or "age_days" not in df.columns:
        latest_published = ""
        oldest_published = ""
        stale_rows = 0
        stale_ratio = 0.0
        is_fresh = True
    else:
        stale_rows = int((df["age_days"] > threshold_days).sum())
        stale_ratio = float(stale_rows / total_rows)
        is_fresh = bool(stale_ratio <= 0.25)

        pub_series = df["published"].dropna().astype(str) if "published" in df.columns else pd.Series(dtype=str)
        latest_published = str(pub_series.max()) if not pub_series.empty else ""
        oldest_published = str(pub_series.min()) if not pub_series.empty else ""

    payload: dict[str, Any] = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": threshold_days,
        "max_stale_ratio_allowed": 0.25,
        "is_fresh": is_fresh,
        "warning": None if is_fresh else f"Cảnh báo: Tỷ lệ bài báo cũ ({stale_ratio:.1%}) vượt quá 25%. Cần cập nhật dữ liệu mới.",
    }

    if report_path is not None:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Dựng Trạm Kiểm Soát Dữ Liệu (Data Quality Gate) với Great Expectations 1.x (mode='ephemeral').

    Thiết lập 4 kỳ vọng (Expectations) bắt buộc:
    1. ExpectTableRowCountToBeBetween: Số lượng bài báo hợp lệ (5 đến 5000).
    2. ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding không để trống.
    3. ExpectColumnValuesToBeUnique: paper_id là khóa duy nhất, không trùng lặp.
    4. ExpectColumnValueLengthsToBeBetween: Trường summary có độ dài tối thiểu 30 ký tự.

    Kết hợp kiểm tra Freshness SLA.
    """
    # 1. Ephemeral Context (chạy tạm trên RAM)
    context = gx.get_context(mode="ephemeral")

    data_source_name = f"papers_source_{report_name}"
    data_asset_name = f"papers_asset_{report_name}"
    batch_def_name = f"papers_batch_{report_name}"

    data_source = context.data_sources.add_pandas(name=data_source_name)
    data_asset = data_source.add_dataframe_asset(name=data_asset_name)
    batch_def = data_asset.add_batch_definition_whole_dataframe(batch_def_name)
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # 2. Tạo Expectation Suite
    suite_name = f"papers_suite_{report_name}"
    suite = gx.ExpectationSuite(name=suite_name)

    # Expectation 1: Row count từ 5 đến 5000
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))

    # Expectation 2: paper_id, title, text_for_embedding không null
    for col in ["paper_id", "title", "text_for_embedding"]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=col))

    # Expectation 3: paper_id unique
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))

    # Expectation 4: summary độ dài tối thiểu 30 ký tự
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    context.suites.add(suite)

    # 3. Thực thi Validation
    try:
        validation_results = batch.validate(suite)
    except Exception:
        val_def_name = f"papers_validation_{report_name}"
        validation_def = gx.ValidationDefinition(
            name=val_def_name,
            data=batch_def,
            suite=suite,
        )
        context.validation_definitions.add(validation_def)
        validation_results = validation_def.run(batch_parameters={"dataframe": df})

    gx_success = bool(getattr(validation_results, "success", False))

    # 4. Kiểm tra Freshness SLA
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    overall_success = gx_success and freshness["is_fresh"]

    results_dict = validation_results.to_json_dict() if hasattr(validation_results, "to_json_dict") else {}

    report_payload: dict[str, Any] = {
        "report_name": report_name,
        "success": overall_success,
        "gx_success": gx_success,
        "freshness": freshness,
        "validation_results": results_dict,
    }

    # Lưu báo cáo quality check vào đĩa
    quality_dir = settings.paths.quality_dir
    quality_dir.mkdir(parents=True, exist_ok=True)

    if report_name == "baseline":
        save_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        save_path = settings.paths.corrupted_quality_report
    else:
        save_path = quality_dir / f"{report_name}_quality_report.json"

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)

    return report_payload