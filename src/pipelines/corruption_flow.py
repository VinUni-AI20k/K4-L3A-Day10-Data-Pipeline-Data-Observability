from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Compare clean, corrupted, and repaired retrieval pipeline states."""
    settings = load_settings()

    clean_df = pd.read_json(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    settings.paths.corrupted_clean_csv.parent.mkdir(parents=True, exist_ok=True)
    corrupted_df.to_csv(settings.paths.corrupted_clean_csv, index=False)
    corrupted_df.to_json(settings.paths.corrupted_clean_json, orient="records", indent=2)

    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )

    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, datetime.now(timezone.utc))
    settings.paths.repaired_clean_csv.parent.mkdir(parents=True, exist_ok=True)
    repaired_df.to_csv(settings.paths.repaired_clean_csv, index=False)
    repaired_df.to_json(settings.paths.repaired_clean_json, orient="records", indent=2)

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        settings.paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_quality["freshness"],
        repaired_quality["freshness"],
    )

    print("Tín hiệu hoàn thành: Corruption flow ran successfully")
    print("Metric                 Baseline  Corrupted  Repaired")
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        print(
            f"{key:<22} {baseline_metrics.get(key, 0):>8.4f}"
            f"  {corrupted_bundle.summary.get(key, 0):>9.4f}"
            f"  {repaired_bundle.summary.get(key, 0):>8.4f}"
        )
    print(f"Corrupted quality: {corrupted_quality['success']}")
    print(f"Repaired quality: {repaired_quality['success']}")
    print(f"Comparison report: {settings.paths.comparison_report}")
