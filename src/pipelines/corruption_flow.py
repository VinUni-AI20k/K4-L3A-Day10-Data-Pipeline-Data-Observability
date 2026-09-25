from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_dataframe
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


COMPARED_METRICS = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")


def _require_phase1_artifacts(settings: Settings) -> None:
    paths = settings.paths
    required = [paths.baseline_metrics, paths.clean_json, paths.eval_testset, paths.raw_records_json]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing Phase 1 artifacts, run `python script/run_phase1.py` first: " + ", ".join(missing)
        )


def _index_and_evaluate(
    settings: Settings,
    df: pd.DataFrame,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
) -> dict[str, Any]:
    """Build collection rieng cho tung trang thai va cham tren CUNG bo test set cua baseline."""
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=metrics_path,
        answers_output_path=answers_path,
    )
    print(f"[flow] Evaluated collection '{index.collection_name}' ({len(index.documents)} docs)")
    return bundle.summary


def _print_comparison(baseline: dict, corrupted: dict, repaired: dict, corrupted_quality: dict, repaired_quality: dict) -> None:
    rows = [(name, f"{baseline[name]:.3f}", f"{corrupted[name]:.3f}", f"{repaired[name]:.3f}") for name in COMPARED_METRICS]
    rows.append(("quality_gate_success", "True", str(corrupted_quality["success"]), str(repaired_quality["success"])))
    header = ("Metric", "Baseline", "Corrupted", "Repaired")
    widths = [max(len(str(row[col])) for row in [header, *rows]) for col in range(4)]
    line = "+".join("-" * (width + 2) for width in widths)
    print(line)
    for row in [header, *rows]:
        print(" | ".join(str(cell).ljust(width) for cell, width in zip(row, widths)))
        if row is header:
            print(line)
    print(line)


def main() -> None:
    """Corruption -> evaluate -> repair -> compare.

    Chung minh Silent Failure: du lieu ban van tra loi binh thuong nhung sai,
    sau do Idempotent Repair tai tao lai du lieu sach tu raw snapshot.
    """
    settings = load_settings()
    paths = settings.paths
    _require_phase1_artifacts(settings)

    # 1. Baseline da duoc Phase 1 do san
    baseline_metrics = read_json(paths.baseline_metrics)
    clean_df = pd.read_json(paths.clean_json)
    print(f"[flow] Loaded baseline: {len(clean_df)} clean rows")

    # 2-3. Tiem loi + luu corrupted artifacts
    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    write_dataframe(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    print(f"[flow] Corrupted: {len(corrupted_df)} rows, log -> {paths.corruption_log.name}")

    # 4. Quality Gate tren du lieu ban: ky vong FAIL.
    #    Production se chan tai day; lab van index tiep de do muc suy giam (Silent Failure).
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, paths.quality_dir / "corrupted_freshness_report.json"
    )
    print(
        f"[flow] Corrupted Quality Gate: success={corrupted_quality['success']} | "
        f"is_fresh={corrupted_freshness['is_fresh']}"
    )
    if corrupted_quality["success"]:
        print("[flow] WARNING: Quality Gate did NOT detect the corruption - review expectations in quality.py.")

    # 5. Do suy giam tren collection papers-corrupted
    corrupted_metrics = _index_and_evaluate(
        settings, corrupted_df, paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers
    )

    # 6. Idempotent Repair: bo qua du lieu hong, tai tao tu raw snapshot bang dung pipeline cleaning.
    #    Chay lai bao nhieu lan cung cho cung ket qua vi nguon (raw) khong doi.
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    write_dataframe(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, paths.quality_dir / "repaired_freshness_report.json"
    )
    print(
        f"[flow] Repaired: {len(repaired_df)} rows | Quality Gate: success={repaired_quality['success']} | "
        f"is_fresh={repaired_freshness['is_fresh']}"
    )
    if not repaired_quality["success"]:
        raise RuntimeError("Repaired data failed the Quality Gate - repair is not trustworthy, stopping.")

    # 7. Danh gia lai tren collection papers-repaired
    repaired_metrics = _index_and_evaluate(
        settings, repaired_df, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers
    )

    # 8. Bao cao doi chieu 3 trang thai
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, repaired_quality)
    print(f"[flow] Done. Report -> {paths.comparison_report}")
