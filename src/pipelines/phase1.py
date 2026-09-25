from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _ensure_clean_artifacts(settings) -> pd.DataFrame:
    raw_path = settings.paths.raw_records_json
    if settings.refresh_source or not raw_path.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(raw_path)

    df = build_clean_dataframe(records, datetime.now(timezone.utc))
    settings.paths.clean_csv.parent.mkdir(parents=True, exist_ok=True)
    settings.paths.clean_json.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(settings.paths.clean_csv, index=False)
    df.to_json(settings.paths.clean_json, orient="records", indent=2)
    return df


def main() -> None:
    """Build the baseline end-to-end pipeline and persist all required artifacts."""
    settings = load_settings()

    clean_df = _ensure_clean_artifacts(settings)
    quality_result = run_data_quality_checks(clean_df, settings, "baseline")
    freshness_report = build_freshness_report(clean_df, settings, settings.paths.freshness_report)

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(clean_df, settings.paths.eval_testset)

    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_records": len(load_raw_records(settings.paths.raw_records_json)),
        "clean_rows": len(clean_df),
        "dropped_rows": max(0, len(load_raw_records(settings.paths.raw_records_json)) - len(clean_df)),
        "collection_name": settings.baseline_collection_name,
        "embedding_model": settings.embedding_model,
        "llm_provider": settings.llm_provider,
        "model_name": settings.model_name,
        "top_k": settings.top_k,
        "test_set_size": len(bundle.answers),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        bundle.summary,
        quality_result,
        freshness_report,
    )

    print(f"Tín hiệu hoàn thành: Baseline pipeline ran on {len(clean_df)} records")
    print(f"Quality: {quality_result['success']}, Freshness: {freshness_report['is_fresh']}, Metrics: {bundle.summary}")
