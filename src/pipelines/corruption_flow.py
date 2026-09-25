from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()

    print("[1/8] Loading baseline metrics, baseline quality report & clean dataset...")
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_quality = read_json(settings.paths.baseline_quality_report)
    clean_df = pd.read_json(settings.paths.clean_json)
    print(f"      -> baseline hit_rate={baseline_metrics['retrieval_hit_rate']:.4f}, clean rows={len(clean_df)}.")

    print("[2/8] Injecting synthetic corruption (6 scenarios) into the clean dataset...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    print(f"      -> corrupted dataset has {len(corrupted_df)} rows (log: {settings.paths.corruption_log}).")

    print("[3/8] Writing corrupted artifacts...")
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))

    print("[4/8] Rebuilding vector index on corrupted data, running quality gate & evaluating...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, embeddings_output_path=settings.paths.corrupted_embeddings_json
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    print(f"      -> corrupted quality gate success={corrupted_quality['success']}")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(
        "      -> hit_rate=%.4f token_f1=%.4f (vs baseline hit_rate=%.4f token_f1=%.4f)"
        % (
            corrupted_bundle.summary["retrieval_hit_rate"],
            corrupted_bundle.summary["mean_token_f1"],
            baseline_metrics["retrieval_hit_rate"],
            baseline_metrics["mean_token_f1"],
        )
    )

    print("[5/8] Repairing dataset from raw source records (idempotent repair)...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, now_utc())
    if repaired_df.empty:
        raise RuntimeError("Repair produced zero valid records from raw source; aborting corruption flow.")
    print(f"      -> repaired dataset rebuilt with {len(repaired_df)} rows from raw records.")

    print("[6/8] Writing repaired artifacts...")
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))

    print("[7/8] Rebuilding vector index on repaired data, running quality gate & evaluating...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, embeddings_output_path=settings.paths.repaired_embeddings_json
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    print(f"      -> repaired quality gate success={repaired_quality['success']}")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print(
        "      -> hit_rate=%.4f token_f1=%.4f"
        % (repaired_bundle.summary["retrieval_hit_rate"], repaired_bundle.summary["mean_token_f1"])
    )

    print("[8/8] Writing 3-state comparison report (baseline vs corrupted vs repaired)...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        baseline_quality=baseline_quality,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        baseline_freshness=baseline_quality["freshness"],
        corrupted_freshness=corrupted_quality["freshness"],
        repaired_freshness=repaired_quality["freshness"],
    )

    print("\nCorruption, repair & comparison flow complete.")
    print(f"  corrupted data    -> {settings.paths.corrupted_clean_csv}")
    print(f"  repaired data     -> {settings.paths.repaired_clean_csv}")
    print(f"  corrupted metrics -> {settings.paths.corrupted_metrics}")
    print(f"  repaired metrics  -> {settings.paths.repaired_metrics}")
    print(f"  comparison report -> {settings.paths.comparison_report}")


if __name__ == "__main__":
    main()
