from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex

COMPARISON_ROWS = [
    ("retrieval_hit_rate", "Hit Rate"),
    ("mean_token_f1", "Token F1"),
    ("judge_accuracy", "Judge Accuracy"),
    ("mean_judge_score", "Judge Score"),
]


def _load_clean_dataframe(settings: Settings) -> pd.DataFrame:
    """Nap lai dataset sach tu Phase 1 (JSON giu nguyen kieu list cho authors/categories)."""
    if not settings.paths.clean_json.exists():
        raise FileNotFoundError(
            f"Khong tim thay {settings.paths.clean_json}. Hay chay `python script/run_phase1.py` truoc."
        )
    return pd.DataFrame(read_json(settings.paths.clean_json))


def _save_dataset(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _evaluate_state(
    settings: Settings,
    df: pd.DataFrame,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
) -> dict[str, Any]:
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=metrics_path,
        answers_output_path=answers_path,
    )
    return bundle.summary


def _print_comparison(baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> None:
    header = f"| {'Chi so':<16} | {'Baseline':>10} | {'Corrupted':>10} | {'Repaired':>10} |"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    for key, label in COMPARISON_ROWS:
        print(
            f"| {label:<16} | {float(baseline.get(key, 0)):>10.4f} "
            f"| {float(corrupted.get(key, 0)):>10.4f} | {float(repaired.get(key, 0)):>10.4f} |"
        )
    print("-" * len(header))


def main() -> None:
    settings = load_settings()
    run_date = now_utc()
    quality_dir = settings.paths.quality_dir
    print("=" * 72)
    print("PHASE 2 - CORRUPTION, REPAIR & COMPARISON (CP4 -> CP5)")
    print("=" * 72)

    # --- 1. Nap baseline ---
    if not settings.paths.baseline_metrics.exists():
        raise FileNotFoundError(
            f"Thieu {settings.paths.baseline_metrics}. Hay chay `python script/run_phase1.py` truoc."
        )
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean_df = _load_clean_dataframe(settings)
    print(f"[1/6] Baseline: {len(clean_df)} dong sach | hit_rate={baseline_metrics.get('retrieval_hit_rate')}")

    # --- 2. Tiem 6 dang loi du lieu ---
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    _save_dataset(corrupted_df, settings.paths.corrupted_clean_csv, settings.paths.corrupted_clean_json)
    print(f"[2/6] Corruption: {len(clean_df)} -> {len(corrupted_df)} dong | log: {settings.paths.corruption_log}")

    # --- 3. Quality Gate phat hien loi ---
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, quality_dir / "freshness_report_corrupted.json"
    )
    print(
        f"[3/6] Quality Gate (corrupted): success={corrupted_quality['success']} "
        f"| {corrupted_quality['unsuccessful_expectations']} expectation FAIL "
        f"| is_fresh={corrupted_freshness['is_fresh']}"
    )
    for item in corrupted_quality["failed_expectations"]:
        print(f"      [ALERT] {item['expectation']} (cot: {item['column']}) -> {item['observed_value']}")

    # --- 4. Do luong suy giam tren du lieu ban ---
    corrupted_metrics = _evaluate_state(
        settings,
        corrupted_df,
        settings.paths.corrupted_embeddings_json,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    print(
        f"[4/6] Corrupted metrics: hit_rate={corrupted_metrics['retrieval_hit_rate']:.4f} "
        f"| token_f1={corrupted_metrics['mean_token_f1']:.4f}"
    )

    # --- 5. Idempotent repair: tai tao tu ban sao luu tho ---
    records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(records, run_date)
    _save_dataset(repaired_df, settings.paths.repaired_clean_csv, settings.paths.repaired_clean_json)
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, quality_dir / "freshness_report_repaired.json"
    )
    repaired_metrics = _evaluate_state(
        settings,
        repaired_df,
        settings.paths.repaired_embeddings_json,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    print(
        f"[5/6] Repair: {len(repaired_df)} dong | quality={repaired_quality['success']} "
        f"| hit_rate={repaired_metrics['retrieval_hit_rate']:.4f}"
    )

    # --- 6. Bao cao doi chieu 3 trang thai ---
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"[6/6] Report: {settings.paths.comparison_report}")
    print()
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics)
    print("PHASE 2 HOAN TAT.")
