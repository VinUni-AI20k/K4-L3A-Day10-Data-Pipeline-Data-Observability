"""Tests for observability/reporting.py — report generation."""
from __future__ import annotations

from pathlib import Path

from observability.reporting import generate_corruption_report, generate_phase1_report


def _sample_quality(success: bool = True) -> dict:
    return {
        "success": success,
        "results": [
            {"expectation": "expect_table_row_count_to_be_between", "success": True, "kwargs": {}},
            {"expectation": "expect_column_values_to_not_be_null", "success": success, "kwargs": {"column": "paper_id"}},
            {"expectation": "expect_column_values_to_be_unique", "success": success, "kwargs": {"column": "paper_id"}},
        ],
    }


def _sample_freshness(is_fresh: bool = True, stale_ratio: float = 0.04) -> dict:
    return {
        "is_fresh": is_fresh,
        "stale_ratio": stale_ratio,
        "stale_rows": 1 if is_fresh else 7,
        "total_rows": 24 if is_fresh else 23,
        "threshold_days": 180,
    }


def test_generate_phase1_report_creates_file(tmp_path):
    out = tmp_path / "phase1.md"
    generate_phase1_report(
        report_path=out,
        source_summary={"record_count": 24, "source": "test"},
        metrics={"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0, "judge_accuracy": 1.0, "mean_judge_score": 5},
        quality=_sample_quality(),
        freshness=_sample_freshness(),
    )
    assert out.exists()
    content = out.read_text()
    assert "Phase 1 Baseline Report" in content
    assert "retrieval_hit_rate" in content


def test_phase1_report_shows_column_names(tmp_path):
    out = tmp_path / "phase1.md"
    generate_phase1_report(
        report_path=out,
        source_summary={"record_count": 24},
        metrics={"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0},
        quality=_sample_quality(),
        freshness=_sample_freshness(),
    )
    content = out.read_text()
    assert "column: paper_id" in content


def test_generate_corruption_report_creates_file(tmp_path):
    out = tmp_path / "corruption.md"
    m = {"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0, "judge_accuracy": 1.0, "mean_judge_score": 5}
    cm = {"retrieval_hit_rate": 0.8, "mean_token_f1": 0.59, "judge_accuracy": 0.6, "mean_judge_score": 3.2}
    generate_corruption_report(
        report_path=out,
        baseline_metrics=m, corrupted_metrics=cm, repaired_metrics=m,
        baseline_quality=_sample_quality(True),
        corrupted_quality=_sample_quality(False),
        repaired_quality=_sample_quality(True),
        baseline_freshness=_sample_freshness(True),
        corrupted_freshness=_sample_freshness(False, 0.30),
        repaired_freshness=_sample_freshness(True),
    )
    assert out.exists()
    content = out.read_text()
    assert "Baseline" in content
    assert "Corrupted" in content
    assert "Repaired" in content


def test_corruption_report_delta_values(tmp_path):
    out = tmp_path / "corruption.md"
    m = {"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0, "judge_accuracy": 1.0, "mean_judge_score": 5}
    cm = {"retrieval_hit_rate": 0.8, "mean_token_f1": 0.59, "judge_accuracy": 0.6, "mean_judge_score": 3.2}
    generate_corruption_report(
        report_path=out,
        baseline_metrics=m, corrupted_metrics=cm, repaired_metrics=m,
        baseline_quality=_sample_quality(), corrupted_quality=_sample_quality(False),
        repaired_quality=_sample_quality(),
        baseline_freshness=_sample_freshness(), corrupted_freshness=_sample_freshness(False, 0.30),
        repaired_freshness=_sample_freshness(),
    )
    content = out.read_text()
    assert "-0.2000" in content
    assert "+0.0000" in content
