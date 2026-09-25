from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _require_artifact(path: Path, instruction: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required artifact does not exist: {path}. {instruction}")


def _write_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Persist a dataframe in both lab artifact formats."""
    write_csv(df, csv_path)
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    write_json(json_path, records)


def main() -> None:
    """Run corruption, degradation measurement, idempotent repair and comparison."""
    settings = load_settings()
    _require_artifact(
        settings.paths.clean_json,
        "Run `python script/run_phase1.py` first.",
    )
    _require_artifact(
        settings.paths.baseline_metrics,
        "Run `python script/run_phase1.py` first.",
    )
    _require_artifact(
        settings.paths.eval_testset,
        "Run `python script/run_phase1.py` first.",
    )

    print("[1/8] Loading baseline artifacts...")
    baseline_df = pd.read_json(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)

    print("[2/8] Injecting six data corruption scenarios...")
    corrupted_df = corrupt_clean_dataframe(
        baseline_df,
        settings.paths.corruption_log,
    )
    _write_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )

    print("[3/8] Running quality checks on corrupted data...")
    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings,
        report_name="corrupted",
    )
    if corrupted_quality["success"]:
        print("Warning: corrupted data unexpectedly passed the quality gate.")
    else:
        print("Expected result: corrupted data failed the quality gate.")

    print("[4/8] Building and evaluating the corrupted Chroma index...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        settings.paths.corrupted_embeddings_json,
        collection_name=settings.corrupted_collection_name,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )

    print("[5/8] Rebuilding clean data idempotently from the raw snapshot...")
    if settings.paths.raw_records_json.exists():
        raw_records = load_raw_records(settings.paths.raw_records_json)
    else:
        raw_records = fetch_source_records(settings)
    repaired_df = build_clean_dataframe(raw_records, run_date=datetime.now(UTC))
    if repaired_df.empty:
        raise RuntimeError("Repair produced no valid records from the raw snapshot.")
    _write_dataframe(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )

    print("[6/8] Running quality checks on repaired data...")
    repaired_quality = run_data_quality_checks(
        repaired_df,
        settings,
        report_name="repaired",
    )

    print("[7/8] Building and evaluating the repaired Chroma index...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        settings.paths.repaired_embeddings_json,
        collection_name=settings.repaired_collection_name,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )

    print("[8/8] Generating the baseline/corrupted/repaired report...")
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_evaluation.summary,
        repaired_metrics=repaired_evaluation.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_quality["freshness"],
        repaired_freshness=repaired_quality["freshness"],
    )

    if not repaired_quality["success"]:
        raise RuntimeError(
            "Repair completed but the repaired dataset still failed its quality gate. "
            f"Inspect {settings.paths.comparison_report}."
        )

    print("Corruption and repair flow completed successfully.")
    print(f"- Baseline rows: {len(baseline_df)}")
    print(f"- Corrupted rows: {len(corrupted_df)}")
    print(f"- Repaired rows: {len(repaired_df)}")
    print(
        "- Retrieval hit rate: "
        f"{float(baseline_metrics['retrieval_hit_rate']):.1%} -> "
        f"{corrupted_evaluation.summary['retrieval_hit_rate']:.1%} -> "
        f"{repaired_evaluation.summary['retrieval_hit_rate']:.1%}"
    )
    print(f"- Report: {settings.paths.comparison_report}")
