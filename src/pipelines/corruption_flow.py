from __future__ import annotations

import logging
import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== BẮT ĐẦU PHA 2: CORRUPTION -> EVALUATE -> REPAIR -> COMPARE ===")
    settings = load_settings()

    # 1. Load baseline metrics & clean dataset
    if not settings.paths.clean_json.exists():
        raise FileNotFoundError(f"Clean dataset not found at {settings.paths.clean_json}. Please run Phase 1 first.")
    clean_df = pd.read_json(settings.paths.clean_json)

    if not settings.paths.baseline_metrics.exists():
        raise FileNotFoundError(f"Baseline metrics not found at {settings.paths.baseline_metrics}. Please run Phase 1 first.")
    baseline_metrics = read_json(settings.paths.baseline_metrics)

    # 2. Inject 6 Synthetic Data Corruptions
    logger.info("1. Tiêm 6 kịch bản lỗi dữ liệu (Data Corruption Suite)...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    corrupted_df.to_json(settings.paths.corrupted_clean_json, orient="records", indent=2, force_ascii=False)
    logger.info(f"   Dữ liệu bị lỗi ({len(corrupted_df)} dòng) đã ghi vào {settings.paths.corrupted_clean_csv}")

    # 3. Observability Gate on Corrupted Data
    logger.info("2. Chốt kiểm dịch Great Expectations 1.x trên dữ liệu bị tiêm lỗi...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        report_path=settings.paths.quality_dir / "corrupted_freshness_report.json",
    )
    logger.info(f"   Quality Gate Status: {'PASS' if corrupted_quality.get('success') else 'FAIL (CẢNH BÁO THÀNH CÔNG)'}")

    # 4. Build Corrupted Index & Evaluate (Demonstrating Silent Failure)
    logger.info("3. Đánh chỉ mục ChromaDB dữ liệu bẩn và đo lường sự sụt giảm của RAG...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    logger.info(f"   Corrupted Hit Rate: {corrupted_bundle.summary.get('retrieval_hit_rate', 0):.2%}")
    logger.info(f"   Corrupted Mean Token F1: {corrupted_bundle.summary.get('mean_token_f1', 0):.4f}")

    # 5. Idempotent Repair from Raw Preservation
    logger.info("4. Kích hoạt cơ chế Phục Hồi An Toàn (Idempotent Repair) từ Raw Data Lineage...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, now_utc())
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    repaired_df.to_json(settings.paths.repaired_clean_json, orient="records", indent=2, force_ascii=False)
    logger.info(f"   Dữ liệu tái phục hồi: {len(repaired_df)} dòng chuẩn sạch.")

    # 6. Observability Gate on Repaired Data
    logger.info("5. Chốt kiểm dịch Great Expectations 1.x trên dữ liệu sau phục hồi...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        report_path=settings.paths.quality_dir / "repaired_freshness_report.json",
    )
    logger.info(f"   Repaired Quality Gate Status: {'PASS' if repaired_quality.get('success') else 'FAIL'}")

    # 7. Build Repaired Index & Evaluate
    logger.info("6. Đánh chỉ mục ChromaDB dữ liệu đã phục hồi và đánh giá lại RAG...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    logger.info(f"   Repaired Hit Rate: {repaired_bundle.summary.get('retrieval_hit_rate', 0):.2%}")
    logger.info(f"   Repaired Mean Token F1: {repaired_bundle.summary.get('mean_token_f1', 0):.4f}")

    # 8. Generate 3-State Comparison Markdown Report
    logger.info("7. Xuất báo cáo đối chiếu 3 trạng thái...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    logger.info(f"   Báo cáo hoàn tất: {settings.paths.comparison_report}")

    # Print summary table to console
    print("\n" + "=" * 70)
    print(" BẢNG ĐỐI CHIẾU 3 TRẠNG THÁI (BASELINE vs CORRUPTED vs REPAIRED)")
    print("=" * 70)
    print(f"{'Chỉ số':<28} | {'🟢 Baseline':<12} | {'🔴 Corrupted':<12} | {'🔵 Repaired':<12}")
    print("-" * 70)
    print(
        f"{'GX 1.x Quality Gate':<28} | {'PASS':<12} | "
        f"{'FAIL' if not corrupted_quality.get('success') else 'PASS':<12} | "
        f"{'PASS' if repaired_quality.get('success') else 'FAIL':<12}"
    )
    print(
        f"{'Freshness SLA':<28} | {'PASS':<12} | "
        f"{'FAIL' if not corrupted_freshness.get('is_fresh') else 'PASS':<12} | "
        f"{'PASS' if repaired_freshness.get('is_fresh') else 'FAIL':<12}"
    )
    print(
        f"{'Retrieval Hit Rate':<28} | "
        f"{baseline_metrics.get('retrieval_hit_rate', 0):.2%}{' ' * 4} | "
        f"{corrupted_bundle.summary.get('retrieval_hit_rate', 0):.2%}{' ' * 4} | "
        f"{repaired_bundle.summary.get('retrieval_hit_rate', 0):.2%}"
    )
    print(
        f"{'Mean Token F1':<28} | "
        f"{baseline_metrics.get('mean_token_f1', 0):.4f}{' ' * 4} | "
        f"{corrupted_bundle.summary.get('mean_token_f1', 0):.4f}{' ' * 4} | "
        f"{repaired_bundle.summary.get('mean_token_f1', 0):.4f}"
    )
    print(
        f"{'LLM Judge Accuracy':<28} | "
        f"{baseline_metrics.get('judge_accuracy', 0):.2%}{' ' * 4} | "
        f"{corrupted_bundle.summary.get('judge_accuracy', 0):.2%}{' ' * 4} | "
        f"{repaired_bundle.summary.get('judge_accuracy', 0):.2%}"
    )
    print("=" * 70 + "\n")
    logger.info("=== PHA 2 (CORRUPTION & REPAIR FLOW) HOÀN TẤT THÀNH CÔNG ===")


if __name__ == "__main__":
    main()
