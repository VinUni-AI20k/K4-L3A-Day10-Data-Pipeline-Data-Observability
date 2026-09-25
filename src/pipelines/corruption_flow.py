from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xay dung corruption -> evaluate -> repair -> compare flow.

    Pseudo-code:
    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe.
    3. Save corrupted artifacts.
    4. Rebuild index va evaluate.
    5. Run quality checks/freshness tren corrupted data.
    6. Repair lai tu raw records.
    7. Evaluate repaired dataset.
    8. Tao comparison report.
    """
    settings = load_settings()
    paths = settings.paths

    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.read_json(paths.clean_json)

    # Corrupt + danh gia tren du lieu hong.
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(corrupted_df, settings, paths.corrupted_embeddings_json)
    corrupted_bundle = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset, paths.corrupted_metrics, paths.corrupted_answers
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality_report")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )

    # Idempotent repair: dung lai tu raw snapshot, ghi de artifact hong.
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    write_csv(repaired_df, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(repaired_df, settings, paths.repaired_embeddings_json)
    repaired_bundle = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset, paths.repaired_metrics, paths.repaired_answers
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality_report")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json"
    )

    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_bundle.summary,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )

    baseline_quality = read_json(paths.baseline_quality_report)
    header = f"{'Metric':<22}{'Baseline':>12}{'Corrupted':>12}{'Repaired':>12}"
    print(header)
    print("-" * len(header))
    print(f"{'Data quality gate':<22}{'PASS' if baseline_quality['success'] else 'FAIL':>12}"
          f"{'PASS' if corrupted_quality['success'] else 'FAIL':>12}"
          f"{'PASS' if repaired_quality['success'] else 'FAIL':>12}")
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy"):
        print(f"{key:<22}{baseline_metrics[key]:>12.3f}{corrupted_bundle.summary[key]:>12.3f}"
              f"{repaired_bundle.summary[key]:>12.3f}")
    print(f"Report: {paths.comparison_report}")
