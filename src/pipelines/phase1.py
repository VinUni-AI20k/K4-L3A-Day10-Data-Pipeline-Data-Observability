from __future__ import annotations

from datetime import UTC, datetime
import json

from core.config import load_settings
from core.utils import write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the complete phase-1 baseline data and retrieval pipeline."""
    settings = load_settings()

    print("[1/7] Loading Crossref source records...")
    records = fetch_source_records(settings)
    if not records:
        raise RuntimeError("Crossref returned no records; the pipeline cannot continue.")

    print("[2/7] Cleaning and persisting the paper dataset...")
    clean_df = build_clean_dataframe(records, run_date=datetime.now(UTC))
    if clean_df.empty:
        raise RuntimeError("No valid records remained after data cleaning.")

    write_csv(clean_df, settings.paths.clean_csv)
    # Convert through pandas JSON first so Timestamp/numpy values become regular
    # JSON primitives before core.utils.write_json serializes the artifact.
    clean_records = json.loads(
        clean_df.to_json(orient="records", date_format="iso")
    )
    write_json(settings.paths.clean_json, clean_records)

    print("[3/7] Running the Great Expectations quality and freshness gate...")
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    freshness = quality["freshness"]
    if not quality["success"]:
        failed_checks = [
            item["name"] for item in quality["expectations"] if not item["success"]
        ]
        if not freshness["is_fresh"]:
            failed_checks.append("freshness")
        details = ", ".join(failed_checks) or "unknown quality check"
        raise RuntimeError(f"Data quality gate failed: {details}.")

    print("[4/7] Building the local Chroma embedding index...")
    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        settings.paths.embeddings_json,
        collection_name=settings.baseline_collection_name,
    )

    print("[5/7] Loading or creating the benchmark test set...")
    test_set = load_or_create_test_set(
        clean_df,
        settings.paths.eval_testset,
        refresh=settings.refresh_test_set,
    )

    print("[6/7] Evaluating retrieval and question answering...")
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    print("[7/7] Generating the phase-1 Markdown report...")
    source_summary = {
        "source": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "removed_records": len(records) - len(clean_df),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "test_samples": len(test_set.samples),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    print("Phase 1 completed successfully.")
    print(f"- Clean papers: {len(clean_df)}")
    print(f"- Benchmark questions: {len(test_set.samples)}")
    print(f"- Retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.1%}")
    print(f"- Report: {settings.paths.baseline_report}")
