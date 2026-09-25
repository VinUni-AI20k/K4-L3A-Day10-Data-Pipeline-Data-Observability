from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import main as run_baseline, save_clean_dataframe
from retrieval.index import LocalEmbeddingIndex


def _clean_signature(df: pd.DataFrame) -> list[tuple[str, str]]:
    return sorted(zip(df["paper_id"], df["text_for_embedding"], strict=True))


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    required = (paths.clean_json, paths.eval_testset, paths.baseline_metrics, paths.raw_records_json, paths.baseline_quality_report, paths.freshness_report)
    if not all(path.exists() for path in required):
        run_baseline()

    baseline_clean = pd.read_json(paths.clean_json)
    records = load_raw_records(paths.raw_records_json)
    repaired = build_clean_dataframe(records, now_utc())
    if _clean_signature(baseline_clean) != _clean_signature(repaired):
        # A refreshed raw snapshot needs a new baseline and benchmark first.
        run_baseline()
        baseline_clean = pd.read_json(paths.clean_json)
        records = load_raw_records(paths.raw_records_json)
        repaired = build_clean_dataframe(records, now_utc())
        if _clean_signature(baseline_clean) != _clean_signature(repaired):
            raise RuntimeError("Raw records and baseline clean data do not match.")

    baseline_metrics = read_json(paths.baseline_metrics)
    test_set = read_json(paths.eval_testset)
    baseline_ids = set(baseline_clean["paper_id"])
    if not test_set or any(not set(item["ground_truth_doc_ids"]).issubset(baseline_ids) for item in test_set):
        raise RuntimeError("Evaluation set does not match the baseline corpus.")

    corrupted = corrupt_clean_dataframe(baseline_clean, paths.corruption_log)
    save_clean_dataframe(corrupted, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted_quality_report")
    corrupted_freshness = build_freshness_report(
        corrupted, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )
    corrupted_index = LocalEmbeddingIndex.build(corrupted, settings, paths.corrupted_embeddings_json)
    corrupted_metrics = evaluate_pipeline(
        settings, corrupted_index, paths.eval_testset, paths.corrupted_metrics, paths.corrupted_answers
    ).summary

    save_clean_dataframe(repaired, paths.repaired_clean_csv, paths.repaired_clean_json)
    repaired_quality = run_data_quality_checks(repaired, settings, "repaired_quality_report")
    repaired_freshness = build_freshness_report(
        repaired, settings, paths.quality_dir / "repaired_freshness_report.json"
    )
    if not repaired_quality["success"]:
        raise RuntimeError("Repaired data failed the quality gate.")
    repaired_index = LocalEmbeddingIndex.build(repaired, settings, paths.repaired_embeddings_json)
    repaired_metrics = evaluate_pipeline(
        settings, repaired_index, paths.eval_testset, paths.repaired_metrics, paths.repaired_answers
    ).summary

    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        baseline_quality=read_json(paths.baseline_quality_report),
        baseline_freshness=read_json(paths.freshness_report),
    )
    print("State       | Hit rate | Token F1 | Quality | Fresh")
    for label, metrics, quality, fresh in (
        ("Baseline", baseline_metrics, read_json(paths.baseline_quality_report), read_json(paths.freshness_report)),
        ("Corrupted", corrupted_metrics, corrupted_quality, corrupted_freshness),
        ("Repaired", repaired_metrics, repaired_quality, repaired_freshness),
    ):
        print(f"{label:<11} | {metrics['retrieval_hit_rate']:>7.1%} | "
              f"{metrics['mean_token_f1']:>8.3f} | "
              f"{'PASS' if quality['success'] else 'FAIL':<7} | "
              f"{'PASS' if fresh['is_fresh'] else 'WARN'}")
    print(f"Report: {paths.comparison_report}")
