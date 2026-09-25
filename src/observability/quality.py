from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chot kiem dich chat luong su dung Great Expectations 1.x.

    1. Khoi tao Ephemeral Context (chay tren RAM).
    2. Add pandas data source, dataframe asset va batch definition.
    3. Thiet lap 4 nhom expectations bat buoc:
       - ExpectTableRowCountToBeBetween: 5 den 5000 dong.
       - ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding.
       - ExpectColumnValuesToBeUnique: paper_id.
       - ExpectColumnValueLengthsToBeBetween: summary >= 30 ky tu.
    4. Validate batch va xuat ket qua JSON vao data/quality/.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = gx.ExpectationSuite(name=f"papers_suite_{report_name}")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    validation_results = batch.validate(suite)
    result_dict = validation_results.to_json_dict()

    if report_name == "baseline":
        report_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        report_path = settings.paths.corrupted_quality_report
    else:
        report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    write_json(report_path, result_dict)
    return result_dict


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path: Path | str) -> dict[str, Any]:
    """Tong hop freshness report theo Freshness SLA.

    1. Tim latest va oldest published date.
    2. Dem so dong stale (age_days > freshness_threshold_days, mac dinh 180 ngay).
    3. Canh bao is_fresh = False neu ty le stale > 25%.
    4. Ghi JSON report vao report_path.
    """
    total_rows = len(df)
    threshold = settings.freshness_threshold_days

    if "age_days" in df.columns:
        stale_rows = int((df["age_days"] > threshold).sum())
    else:
        stale_rows = 0

    stale_ratio = float(stale_rows / total_rows) if total_rows > 0 else 0.0
    is_fresh = bool(stale_ratio <= 0.25)

    latest_published = str(df["published"].max()) if not df.empty and "published" in df.columns else ""
    oldest_published = str(df["published"].min()) if not df.empty and "published" in df.columns else ""

    payload: dict[str, Any] = {
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": threshold,
        "is_fresh": is_fresh,
        "latest_published": latest_published,
        "oldest_published": oldest_published,
    }

    target = Path(report_path)
    write_json(target, payload)
    return payload

