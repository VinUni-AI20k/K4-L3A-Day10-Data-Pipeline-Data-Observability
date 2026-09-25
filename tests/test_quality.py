from __future__ import annotations

import pandas as pd

from core.utils import read_json
from observability.quality import _date_text, build_freshness_report, run_data_quality_checks


def test_quality_gate_passes_for_contract_dataframe(clean_df, settings):
    report = run_data_quality_checks(clean_df, settings, "baseline")
    assert report["success"] is True
    assert report["report_name"] == "baseline"
    assert report["row_count"] == len(clean_df)
    assert report["freshness"]["is_fresh"] is True
    assert report["freshness"]["max_stale_ratio"] == 0.25
    assert report["freshness"]["stale_rows"] == 1
    assert {item["type"] for item in report["expectations"]} >= {
        "expect_table_row_count_to_be_between",
        "expect_column_values_to_not_be_null",
        "expect_column_values_to_be_unique",
        "expect_column_value_lengths_to_be_between",
    }
    saved = read_json(settings.paths.baseline_quality_report)
    assert saved["success"] is True


def test_quality_gate_fails_on_short_summary_and_duplicate_ids(clean_df, settings):
    broken = clean_df.copy()
    broken.loc[0, "summary"] = "too short"
    broken.loc[1, "paper_id"] = broken.loc[0, "paper_id"]
    report = run_data_quality_checks(broken, settings, "corrupted")
    assert report["success"] is False
    assert settings.paths.corrupted_quality_report.exists()

    unnamed = run_data_quality_checks(broken, settings, "test")
    assert unnamed["success"] is False
    assert (settings.paths.quality_dir / "test_quality_report.json").exists()


def test_freshness_sla_flags_a_stale_corpus(clean_df, settings, tmp_path):
    stale = clean_df.copy()
    stale["age_days"] = [10, 400, 400, 400, 400, 20]
    report_path = tmp_path / "freshness_report_corrupted.json"
    payload = build_freshness_report(stale, settings, report_path)
    assert payload["is_fresh"] is False
    assert payload["stale_rows"] == 4
    assert payload["total_rows"] == 6
    assert payload["latest_published"] == "2026-07-01"
    assert payload["oldest_published"] == "2025-01-01"
    assert read_json(report_path)["is_fresh"] is False


def test_freshness_without_dates_is_not_fresh(settings, tmp_path):
    frame = pd.DataFrame({"age_days": [10, 20]})
    payload = build_freshness_report(frame, settings, tmp_path / "freshness.json")
    assert payload["latest_published"] is None
    assert payload["oldest_published"] is None
    assert payload["is_fresh"] is True

    dated = pd.DataFrame({"published": ["2026-08-01", "2020-01-01"]})
    from_published = build_freshness_report(dated, settings, tmp_path / "from_published.json")
    assert from_published["total_rows"] == 2
    assert from_published["oldest_published"] == "2020-01-01"

    empty = build_freshness_report(pd.DataFrame(), settings, tmp_path / "empty.json")
    assert empty["total_rows"] == 0
    assert empty["is_fresh"] is False
    assert empty["stale_ratio"] == 1.0
    assert _date_text(None) is None
    assert _date_text(float("nan")) is None
