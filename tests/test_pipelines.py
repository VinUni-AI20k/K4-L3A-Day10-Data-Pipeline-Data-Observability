"""Smoke tests for pipeline orchestrators via mocking heavy I/O."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_settings(tmp_path: Path):
    s = MagicMock()
    s.llm_provider = "mock"
    s.model_name = "mock"
    s.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    s.top_k = 3
    s.freshness_threshold_days = 180
    s.source_api = "https://api.crossref.org/works"
    s.source_query = "knowledge graph"
    s.source_filter = "type:journal-article"
    s.max_results = 10
    s.refresh_source = False
    s.refresh_test_set = False

    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    (data / "clean").mkdir(parents=True)
    (data / "chroma").mkdir(parents=True)
    (data / "embeddings").mkdir(parents=True)
    (data / "eval").mkdir(parents=True)
    (data / "results").mkdir(parents=True)
    (data / "quality").mkdir(parents=True)
    (data / "reports").mkdir(parents=True)

    s.paths.raw_api_response   = data / "raw/crossref_response.json"
    s.paths.raw_records_json   = data / "raw/crossref_records.json"
    s.paths.clean_csv          = data / "clean/papers_clean.csv"
    s.paths.clean_json         = data / "clean/papers_clean.json"
    s.paths.chroma_dir         = data / "chroma"
    s.baseline_collection_name  = "papers-baseline"
    s.corrupted_collection_name = "papers-corrupted"
    s.repaired_collection_name  = "papers-repaired"
    s.paths.baseline_embeddings_json = data / "embeddings/papers_embeddings.json"
    s.paths.corrupted_embeddings_json = data / "embeddings/papers_embeddings_corrupted.json"
    s.paths.repaired_embeddings_json = data / "embeddings/papers_embeddings_repaired.json"
    s.paths.embeddings_json    = data / "embeddings/papers_embeddings.json"
    s.paths.eval_testset       = data / "eval/test_set.json"
    s.paths.baseline_metrics   = data / "results/baseline_metrics.json"
    s.paths.baseline_answers   = data / "results/baseline_answers.json"
    s.paths.corrupted_metrics  = data / "results/corrupted_metrics.json"
    s.paths.corrupted_answers  = data / "results/corrupted_answers.json"
    s.paths.repaired_metrics   = data / "results/repaired_metrics.json"
    s.paths.repaired_answers   = data / "results/repaired_answers.json"
    s.paths.quality_dir        = data / "quality"
    s.paths.baseline_quality_report = data / "quality/baseline_quality_report.json"
    s.paths.corrupted_quality_report = data / "quality/corrupted_quality_report.json"
    s.paths.freshness_report   = data / "quality/freshness_report.json"
    s.paths.corruption_log     = data / "results/corruption_log.json"
    s.paths.corrupted_clean_csv  = data / "clean/papers_clean_corrupted.csv"
    s.paths.corrupted_clean_json = data / "clean/papers_clean_corrupted.json"
    s.paths.repaired_clean_csv   = data / "clean/papers_clean_repaired.csv"
    s.paths.repaired_clean_json  = data / "clean/papers_clean_repaired.json"
    s.paths.phase1_report      = data / "reports/phase1_report.md"
    s.paths.baseline_report    = data / "reports/phase1_report.md"
    s.paths.comparison_report  = data / "reports/corruption_report.md"
    return s


# ── phase1 pipeline ──────────────────────────────────────────────────────────

def test_phase1_main_runs(clean_df, sample_records, tmp_path):
    """phase1.main() runs end-to-end with mocked settings and real clean_df."""
    settings = _make_settings(tmp_path)

    with (
        patch("pipelines.phase1.load_settings", return_value=settings),
        patch("pipelines.phase1.fetch_source_records", return_value=sample_records),
        patch("pipelines.phase1.build_clean_dataframe", return_value=clean_df),
        patch("pipelines.phase1.write_csv"),
        patch("pipelines.phase1.write_json"),
    ):
        from pipelines.phase1 import main
        main()  # should not raise

    assert settings.paths.phase1_report.exists()
    assert settings.paths.baseline_metrics.exists()


# ── corruption flow pipeline ──────────────────────────────────────────────────

def test_corruption_flow_main_runs(clean_df, sample_records, tmp_path):
    """corruption_flow.main() runs end-to-end with mocked baseline artifacts."""
    settings = _make_settings(tmp_path)

    # Pre-write baseline artifacts so the guard check passes
    baseline_m = {"retrieval_hit_rate": 1.0, "mean_token_f1": 1.0,
                  "judge_accuracy": 1.0, "mean_judge_score": 5, "samples": 10}
    baseline_q = {"success": True, "results": [], "statistics": {"evaluated": 6, "successful": 6}}
    baseline_f = {"is_fresh": True, "stale_ratio": 0.04, "stale_rows": 1,
                  "total_rows": 24, "threshold_days": 180}
    settings.paths.baseline_metrics.write_text(json.dumps(baseline_m))
    settings.paths.clean_json.write_text(clean_df.to_json(orient="records"))
    settings.paths.baseline_quality_report.write_text(json.dumps(baseline_q))
    settings.paths.freshness_report.write_text(json.dumps(baseline_f))

    # Pre-generate test set so evaluate_pipeline can load it
    from evaluation.testset import build_test_set
    build_test_set(clean_df, settings.paths.eval_testset)

    with (
        patch("pipelines.corruption_flow.load_settings", return_value=settings),
        patch("pipelines.corruption_flow.load_raw_records", return_value=sample_records),
        patch("pipelines.corruption_flow.build_clean_dataframe", return_value=clean_df),
        patch("pipelines.corruption_flow.write_csv"),
        patch("pipelines.corruption_flow.write_json"),
    ):
        from pipelines.corruption_flow import main
        main()

    assert settings.paths.comparison_report.exists()


def test_corruption_flow_guard_raises_without_baseline(tmp_path):
    """Guard check raises RuntimeError if baseline_metrics missing."""
    settings = _make_settings(tmp_path)
    # baseline_metrics does NOT exist (don't create the file)

    with (
        patch("pipelines.corruption_flow.load_settings", return_value=settings),
    ):
        from pipelines.corruption_flow import main
        # baseline_metrics path doesn't exist → RuntimeError
        with pytest.raises(RuntimeError, match="Baseline artifacts not found"):
            main()
