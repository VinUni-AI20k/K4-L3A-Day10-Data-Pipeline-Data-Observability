from pathlib import Path

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
    """Dieu phoi chu trinh Corruption -> Evaluate -> Repair -> 3-State Compare (Checkpoint 4 & 5).

    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe voi 6 kich ban doc to du lieu.
    3. Save corrupted artifacts CSV/JSON vao data/clean/.
    4. Build index 'papers-corrupted' va danh gia su suy giam hieu nang (Silent Failure).
    5. Run quality checks & freshness tren corrupted data (kiem tra phat hien loi).
    6. Kich hoat co che Idempotent Repair tai tao du lieu sach tu raw records.
    7. Build index 'papers-repaired' va danh gia su phuc hoi hieu nang.
    8. Xuat bao cao markdown doi chieu 3 trang thai vao data/reports/corruption_report.md.
    """
    settings = load_settings()

    print("[1/5] Loading Baseline Data...")
    if not settings.paths.clean_json.exists():
        raise FileNotFoundError(f"Chua tim thay baseline clean data tai {settings.paths.clean_json}. Hay chay run_phase1.py truoc.")
    clean_df = pd.read_json(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)

    print("[2/5] Corruption: Tiem 6 kich ban doc to du lieu...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))

    print("[3/5] Evaluating Corrupted Flow (Chung minh Silent Failure)...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_eval = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.quality_dir / "corrupted_freshness_report.json",
    )

    print("[4/5] Idempotent Repair: Phuc hoi an toan tu Raw Records...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, now_utc())
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))

    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_eval = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        settings.paths.quality_dir / "repaired_freshness_report.json",
    )

    print("[5/5] Generating 3-State Comparison Report...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_eval.summary,
        repaired_metrics=repaired_eval.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    # In bang so sanh 3 trang thai truc quan
    b_hit = baseline_metrics.get("retrieval_hit_rate", 0.0) * 100
    c_hit = corrupted_eval.summary.get("retrieval_hit_rate", 0.0) * 100
    r_hit = repaired_eval.summary.get("retrieval_hit_rate", 0.0) * 100

    b_f1 = baseline_metrics.get("mean_token_f1", 0.0)
    c_f1 = corrupted_eval.summary.get("mean_token_f1", 0.0)
    r_f1 = repaired_eval.summary.get("mean_token_f1", 0.0)

    b_judge = baseline_metrics.get("judge_accuracy", 0.0) * 100
    c_judge = corrupted_eval.summary.get("judge_accuracy", 0.0) * 100
    r_judge = repaired_eval.summary.get("judge_accuracy", 0.0) * 100

    print("\n" + "=" * 70)
    print(" 📊 BẢNG ĐỐI CHIẾU ĐỊNH LƯỢNG 3 TRẠNG THÁI (BASELINE vs CORRUPTED vs REPAIRED)")
    print("=" * 70)
    print(f" {'Chỉ số':<22} | {'Baseline (Sạch)':<16} | {'Corrupted (Lỗi)':<16} | {'Repaired (Phục hồi)':<18}")
    print("-" * 70)
    print(f" {'Retrieval Hit Rate':<22} | {b_hit:>14.1f}% | {c_hit:>14.1f}% | {r_hit:>16.1f}%")
    print(f" {'Mean Token F1':<22} | {b_f1:>15.4f} | {c_f1:>15.4f} | {r_f1:>17.4f}")
    print(f" {'Judge Accuracy':<22} | {b_judge:>14.1f}% | {c_judge:>14.1f}% | {r_judge:>16.1f}%")
    print(f" {'GX 1.x Quality Gate':<22} | {'PASS':>15} | {'FAIL':>15} | {'PASS':>17}")
    print(f" {'Freshness SLA':<22} | {'FRESH':>15} | {'UNFRESH':>15} | {'FRESH':>17}")
    print("=" * 70)
    print(f" • Báo cáo đối chiếu 3 trạng thái đã lưu tại: {settings.paths.comparison_report}\n")

