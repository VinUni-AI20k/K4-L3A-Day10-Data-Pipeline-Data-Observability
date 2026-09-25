from __future__ import annotations

from datetime import UTC

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the clean baseline from raw lineage through evaluation/reporting."""
    settings = load_settings()
    run_time = now_utc()

    if settings.paths.raw_records_json.exists() and not settings.refresh_source:
        records = load_raw_records(settings.paths.raw_records_json)
        source_mode = "offline parsed snapshot"
    else:
        records = fetch_source_records(settings)
        source_mode = "live API" if settings.refresh_source else "offline API snapshot"

    clean_df = build_clean_dataframe(records, run_time)
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = quality["freshness"]
    if not quality["success"]:
        raise RuntimeError(
            "Baseline data failed the quality/freshness gate; see "
            f"{settings.paths.baseline_quality_report}."
        )

    load_or_create_test_set(
        clean_df,
        settings.paths.eval_testset,
        refresh=settings.refresh_test_set,
    )
    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )

    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary={
            "source": settings.source_api,
            "mode": source_mode,
            "records": len(records),
            "clean_records": len(clean_df),
            "run_time_utc": run_time.astimezone(UTC).isoformat(),
            "raw_snapshot": str(settings.paths.raw_records_json.relative_to(settings.paths.project_dir)),
        },
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    print("Phase 1 completed successfully")
    print(f"  clean rows: {len(clean_df)}")
    print(f"  quality gate: {'PASSED' if quality['success'] else 'FAILED'}")
    print(f"  retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.1%}")
    print(f"  mean token F1: {evaluation.summary['mean_token_f1']:.3f}")
    print(f"  report: {settings.paths.baseline_report}")
