"""
tests/test_corruption.py — kiểm tra corrupt_clean_dataframe.
"""
from __future__ import annotations

import json

import pytest

from ingestion.corruption import corrupt_clean_dataframe

REQUIRED_CORRUPTION_TYPES = {
    "drop_latest",
    "blank_summary",
    "inject_noise",
    "truncate_title",
    "stale_date",
    "duplicate_rows",
}


class TestCorruptCleanDataframe:
    def test_returns_dataframe(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        import pandas as pd
        assert isinstance(result, pd.DataFrame)

    def test_does_not_modify_original(self, clean_df, tmp_path):
        original_len = len(clean_df)
        original_titles = clean_df["title"].tolist()
        log_path = tmp_path / "corruption_log.json"
        corrupt_clean_dataframe(clean_df, log_path)
        assert len(clean_df) == original_len
        assert clean_df["title"].tolist() == original_titles

    def test_log_file_created(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        corrupt_clean_dataframe(clean_df, log_path)
        assert log_path.exists()

    def test_log_has_6_corruption_types(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        corrupt_clean_dataframe(clean_df, log_path)
        log = json.loads(log_path.read_text())
        types = {entry["type"] for entry in log}
        assert types == REQUIRED_CORRUPTION_TYPES, f"Missing types: {REQUIRED_CORRUPTION_TYPES - types}"

    def test_log_entries_have_required_fields(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        corrupt_clean_dataframe(clean_df, log_path)
        log = json.loads(log_path.read_text())
        for entry in log:
            assert "type" in entry
            assert "num_rows" in entry
            assert "paper_ids" in entry
            assert entry["num_rows"] >= 1

    def test_some_summaries_blanked(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        assert (result["summary"] == "").any()

    def test_no_none_in_summary(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        assert result["summary"].notna().all()

    def test_some_titles_truncated_below_8(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        assert (result["title"].str.len() < 8).any()

    def test_duplicate_rows_exist(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        assert result["paper_id"].duplicated().any()

    def test_stale_age_days_over_180(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        assert (result["age_days"] > 180).any()

    def test_text_for_embedding_rebuilt(self, clean_df, tmp_path):
        log_path = tmp_path / "corruption_log.json"
        result = corrupt_clean_dataframe(clean_df, log_path)
        for val in result["text_for_embedding"]:
            lines = val.strip().split("\n")
            assert len(lines) == 5

    def test_deterministic_with_seed(self, clean_df, tmp_path):
        """Chạy 2 lần phải ra cùng kết quả."""
        log1 = tmp_path / "log1.json"
        log2 = tmp_path / "log2.json"
        r1 = corrupt_clean_dataframe(clean_df, log1)
        r2 = corrupt_clean_dataframe(clean_df, log2)
        assert r1["paper_id"].tolist() == r2["paper_id"].tolist()
        assert r1["summary"].tolist() == r2["summary"].tolist()
