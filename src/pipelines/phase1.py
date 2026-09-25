from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import ensure_parent, now_utc, write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def save_clean_dataframe(df: pd.DataFrame, csv_path, json_path) -> None:
    """Write both reproducible clean artifacts from one in-memory DataFrame."""
    write_csv(df, csv_path)
    ensure_parent(json_path)
    df.to_json(json_path, orient="records", force_ascii=False, indent=2, date_format="iso")


def main() -> None:
    settings = load_settings()
    paths = settings.paths

    if settings.refresh_source or not paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(paths.raw_records_json)
    if not records:
        raise RuntimeError("No raw records are available for the baseline pipeline.")

    clean = build_clean_dataframe(records, now_utc())
    if clean.empty:
        raise RuntimeError("Cleaning produced no papers.")
    save_clean_dataframe(clean, paths.clean_csv, paths.clean_json)

    quality = run_data_quality_checks(clean, settings, "baseline_quality_report")
    freshness = build_freshness_report(clean, settings, paths.freshness_report)
    if not quality["success"]:
        raise RuntimeError("Baseline data failed the quality gate; see baseline_quality_report.json.")

    test_set = load_or_create_test_set(
        clean,
        paths.eval_testset,
        refresh=settings.refresh_test_set or settings.refresh_source,
    )
    clean_ids = set(clean["paper_id"])
    if any(not set(item["ground_truth_doc_ids"]).issubset(clean_ids) for item in test_set):
        test_set = load_or_create_test_set(clean, paths.eval_testset, refresh=True)
    if not test_set:
        raise RuntimeError("The evaluation set is empty.")

    index = LocalEmbeddingIndex.build(clean, settings, paths.embeddings_json)
    result = evaluate_pipeline(
        settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers
    )
    generate_phase1_report(
        paths.baseline_report,
        {
            "source_api": settings.source_api,
            "query": settings.source_query,
            "raw_records_count": len(records),
        },
        result.summary,
        quality,
        freshness,
    )
    print(f"Baseline: {len(clean)} papers, {len(test_set)} questions, "
          f"hit rate {result.summary['retrieval_hit_rate']:.1%}, "
          f"token F1 {result.summary['mean_token_f1']:.3f}")
    print(f"Report: {paths.baseline_report}")
