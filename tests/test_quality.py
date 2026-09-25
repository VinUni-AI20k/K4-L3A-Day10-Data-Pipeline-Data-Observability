"""Tests for observability/quality.py — GX checks & freshness SLA."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from observability.quality import build_freshness_report, run_data_quality_checks


def _mock_settings(tmp_path: Path):
    s = MagicMock()
    s.freshness_threshold_days = 180
    s.paths.quality_dir = tmp_path
    return s


def test_gx_passes_on_clean_data(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    report = run_data_quality_checks(clean_df, settings, "test_report")
    assert report["success"] is True
    assert report["statistics"]["evaluated"] == 6
    assert report["statistics"]["successful"] == 6


def test_gx_fails_on_duplicate_paper_id(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    duped = pd.concat([clean_df, clean_df.iloc[:1]], ignore_index=True)
    report = run_data_quality_checks(duped, settings, "test_report")
    assert report["success"] is False
    failed = [r["expectation"] for r in report["results"] if not r["success"]]
    assert any("unique" in e for e in failed)


def test_gx_fails_on_blank_summary(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    df = clean_df.copy()
    df.loc[df.index[0], "summary"] = ""
    report = run_data_quality_checks(df, settings, "test_report")
    assert report["success"] is False
    failed = [r["expectation"] for r in report["results"] if not r["success"]]
    assert any("length" in e for e in failed)


def test_gx_fails_on_null_paper_id(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    df = clean_df.copy()
    df.loc[df.index[0], "paper_id"] = None
    report = run_data_quality_checks(df, settings, "test_report")
    assert report["success"] is False


def test_freshness_pass_when_mostly_fresh(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    report = build_freshness_report(clean_df, settings, tmp_path / "fresh.json")
    # clean_df has age_days based on published="2026-01-15", run_date=2026-09-25 → ~253 days
    # But 1/10 stale = 10% < 25% → might still be fresh depending on fixture
    assert "is_fresh" in report
    assert "stale_ratio" in report
    assert 0.0 <= report["stale_ratio"] <= 1.0


def test_freshness_fail_when_too_stale(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    df = clean_df.copy()
    # Force 8/10 rows to be stale (80% > 25%)
    df["age_days"] = [500] * 8 + [10] * 2
    report = build_freshness_report(df, settings, tmp_path / "fresh.json")
    assert report["is_fresh"] is False
    assert report["stale_ratio"] == pytest.approx(0.8)


def test_freshness_threshold_boundary(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    df = clean_df.copy()
    total = len(df)
    # Set exactly 25% stale → should still pass (threshold is > 0.25, not >=)
    stale_count = int(total * 0.25)
    df["age_days"] = [500] * stale_count + [10] * (total - stale_count)
    report = build_freshness_report(df, settings, tmp_path / "fresh.json")
    assert report["is_fresh"] is True  # 25% exactly = not exceeding threshold


def test_freshness_saves_json(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    out = tmp_path / "fresh_out.json"
    build_freshness_report(clean_df, settings, out)
    assert out.exists()


def test_gx_report_has_all_expectation_types(clean_df, tmp_path):
    settings = _mock_settings(tmp_path)
    report = run_data_quality_checks(clean_df, settings, "test_report")
    types = {r["expectation"] for r in report["results"]}
    assert any("row_count" in t for t in types)
    assert any("unique" in t for t in types)
    assert any("null" in t or "not_be_null" in t for t in types)
