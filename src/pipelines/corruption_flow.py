from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    run_date = datetime.now(timezone.utc)

    print("=== Corruption Flow: Corrupt → Evaluate → Repair → Compare ===")

    if not settings.paths.baseline_metrics.exists() or not settings.paths.clean_json.exists():
        raise RuntimeError(
            "Baseline artifacts not found. Run `python script/run_phase1.py` first."
        )

    # Load baseline metrics and quality
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    baseline_quality = read_json(settings.paths.baseline_quality_report)
    baseline_freshness = read_json(settings.paths.freshness_report)
    print(f"Baseline hit_rate={baseline_metrics['retrieval_hit_rate']:.4f}")

    # Load clean baseline data
    clean_df = pd.read_json(settings.paths.clean_json)

    # --- CORRUPT ---
    print("\n[1/6] Injecting data corruption...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    print(f"      Corrupted df: {len(corrupted_df)} rows (log → {settings.paths.corruption_log})")

    # Build corrupted index + evaluate
    print("[2/6] Building corrupted index and evaluating...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, settings.paths.corrupted_embeddings_json
    )
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    cm = corrupted_bundle.summary
    print(f"      hit_rate={cm['retrieval_hit_rate']:.4f}  token_f1={cm['mean_token_f1']:.4f}")

    # Quality on corrupted
    print("[3/6] Quality checks on corrupted data...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality_report")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness_report.json"
    )
    print(f"      GX success={corrupted_quality['success']}  is_fresh={corrupted_freshness['is_fresh']}")

    # --- REPAIR ---
    print("\n[4/6] Repairing from raw snapshot (idempotent)...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date)
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    print(f"      Repaired df: {len(repaired_df)} rows")

    # Build repaired index + evaluate
    print("[5/6] Building repaired index and evaluating...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, settings.paths.repaired_embeddings_json
    )
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    rm = repaired_bundle.summary
    print(f"      hit_rate={rm['retrieval_hit_rate']:.4f}  token_f1={rm['mean_token_f1']:.4f}")

    # Quality on repaired
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality_report")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, settings.paths.quality_dir / "repaired_freshness_report.json"
    )

    # --- REPORT ---
    print("\n[6/6] Generating comparison report...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=cm,
        repaired_metrics=rm,
        baseline_quality=baseline_quality,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        baseline_freshness=baseline_freshness,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print("\n=== 3-State Comparison ===")
    print(f"{'Metric':<25} {'Baseline':>10} {'Corrupted':>10} {'Repaired':>10}")
    print("-" * 60)
    for key in ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy"]:
        print(f"{key:<25} {baseline_metrics.get(key, 0):>10.4f} {cm.get(key, 0):>10.4f} {rm.get(key, 0):>10.4f}")
    print(f"\nReport → {settings.paths.comparison_report}")
    print("=== Corruption Flow Complete ===")


if __name__ == "__main__":
    main()
