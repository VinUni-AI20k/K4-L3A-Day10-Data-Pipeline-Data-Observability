from __future__ import annotations

from datetime import datetime, timezone

from core.config import load_settings
from core.utils import write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from evaluation.testset import build_test_set
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    run_date = datetime.now(timezone.utc)

    print("=== Phase 1: Baseline Pipeline ===")

    # 1. Ingest
    print("[1/7] Loading records...")
    records = fetch_source_records(settings)
    print(f"      Loaded {len(records)} records")

    # 2. Clean
    print("[2/7] Cleaning data...")
    df = build_clean_dataframe(records, run_date)
    print(f"      Clean dataframe: {len(df)} rows")

    # 3. Save clean artifacts
    print("[3/7] Saving clean artifacts...")
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    # 4. Build vector index
    print("[4/7] Building ChromaDB index (papers-baseline)...")
    index = LocalEmbeddingIndex.build(df, settings, settings.paths.embeddings_json)
    print(f"      Indexed {len(index.documents)} documents")

    # 5. Build / load test set
    print("[5/7] Building evaluation test set...")
    build_test_set(df, settings.paths.eval_testset)

    # 6. Evaluate
    print("[6/7] Evaluating baseline pipeline...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    m = bundle.summary
    print(f"      hit_rate={m['retrieval_hit_rate']:.4f}  token_f1={m['mean_token_f1']:.4f}")

    # 7. Quality checks + freshness
    print("[7/7] Running data quality checks...")
    quality = run_data_quality_checks(df, settings, "baseline_quality_report")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
    print(f"      GX success={quality['success']}  is_fresh={freshness['is_fresh']}")

    # Generate report
    source_summary = {
        "record_count": len(df),
        "source": settings.source_api,
        "query": settings.source_query,
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    print(f"\nBaseline report → {settings.paths.baseline_report}")
    print("=== Phase 1 Complete ===")


if __name__ == "__main__":
    main()
