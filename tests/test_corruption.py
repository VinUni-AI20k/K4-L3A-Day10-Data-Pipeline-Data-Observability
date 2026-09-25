"""Tests for ingestion/corruption.py — 6 mutation types & rebuild."""
from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.corruption import corrupt_clean_dataframe


def test_drop_latest_removes_20_percent(clean_df, tmp_path):
    n_before = len(clean_df)
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    n_drop = n_before // 5
    # After drop + 3 dupes added at end
    assert len(corrupted) == n_before - n_drop + 3


def test_blank_summary_on_first_three(clean_df, tmp_path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    blanked = corrupted[corrupted["summary"] == ""]
    assert len(blanked) >= 3


def test_noise_injected_in_summary(clean_df, tmp_path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    noisy = corrupted[corrupted["summary"].str.contains("####NOISE####", na=False)]
    assert len(noisy) == 3


def test_truncated_titles_exist(clean_df, tmp_path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    # After drop_latest (20%), truncate applies to rows 6:9 of remaining df
    # With 10 fixture records: drop 2, remaining 8 → rows 6,7 = 2 truncated
    short = corrupted[corrupted["title"].str.len() <= 7]
    assert len(short) >= 2


def test_stale_dates_present(clean_df, tmp_path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    stale = corrupted[corrupted["age_days"] > 180]
    assert len(stale) >= 6


def test_duplicate_paper_ids_present(clean_df, tmp_path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    dupes = corrupted[corrupted["paper_id"].duplicated(keep=False)]
    assert len(dupes) >= 3


def test_corruption_log_written(clean_df, tmp_path):
    log_path = tmp_path / "corruption_log.json"
    corrupt_clean_dataframe(clean_df, log_path)
    assert log_path.exists()


def test_corruption_log_has_six_entries(clean_df, tmp_path):
    import json
    log_path = tmp_path / "corruption_log.json"
    corrupt_clean_dataframe(clean_df, log_path)
    log = json.loads(log_path.read_text())
    assert len(log) == 6


def test_corruption_log_types(clean_df, tmp_path):
    import json
    log_path = tmp_path / "corruption_log.json"
    corrupt_clean_dataframe(clean_df, log_path)
    log = json.loads(log_path.read_text())
    types = {e["type"] for e in log}
    expected = {"drop_latest", "blank_summary", "inject_noise", "truncate_title", "stale_date", "duplicate_rows"}
    assert types == expected


def test_text_for_embedding_rebuilt(clean_df, tmp_path):
    corrupted = corrupt_clean_dataframe(clean_df, tmp_path / "log.json")
    assert "text_for_embedding" in corrupted.columns
    # Non-blank rows should have text_for_embedding starting with "Title:"
    non_blank = corrupted[corrupted["title"].str.len() > 7]
    assert all(non_blank["text_for_embedding"].str.startswith("Title:"))
