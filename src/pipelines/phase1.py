from __future__ import annotations

import logging
from core.config import load_settings
from core.utils import now_utc, write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== BẮT ĐẦU PHA 1: BASELINE PIPELINE ===")
    settings = load_settings()

    # 1. Ingestion: load or fetch raw records
    logger.info("1. Đang nạp dữ liệu thô từ Crossref (Dual-Mode)...")
    records = fetch_source_records(settings)
    logger.info(f"   Đã tải {len(records)} bản ghi bài báo.")

    # 2. Cleaning & Transformation
    logger.info("2. Làm sạch & chuẩn hóa dữ liệu pre-embedding...")
    df = build_clean_dataframe(records, now_utc())
    write_csv(df, settings.paths.clean_csv)
    df.to_json(settings.paths.clean_json, orient="records", indent=2, force_ascii=False)
    logger.info(f"   Đã xuất dữ liệu sạch: {len(df)} dòng vào {settings.paths.clean_csv}")

    # 3. Data Observability Gate (GX 1.x & Freshness)
    logger.info("3. Chạy Data Quality Gate (Great Expectations 1.x) & Freshness SLA...")
    quality = run_data_quality_checks(df, settings, report_name="baseline")
    freshness = build_freshness_report(df, settings, report_path=settings.paths.freshness_report)
    logger.info(f"   Quality Gate Status: {'PASS' if quality.get('success') else 'FAIL'}")
    logger.info(f"   Freshness SLA: Fresh = {freshness.get('is_fresh')}")

    # 4. Build ChromaDB Vector Index
    logger.info("4. Tạo embedding & đánh chỉ mục Vector Store (ChromaDB)...")
    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=settings.paths.embeddings_json)
    logger.info(f"   Đã index thành công vào collection '{settings.baseline_collection_name}'")

    # 5. Build Test Set Benchmark
    logger.info("5. Chuẩn bị bộ đề thi Benchmark (10 câu hỏi qua 4 nghiệp vụ)...")
    if not settings.paths.eval_testset.exists() or settings.refresh_test_set:
        build_test_set(df, settings.paths.eval_testset)
    logger.info(f"   Test set sẵn sàng tại: {settings.paths.eval_testset}")

    # 6. Evaluation
    logger.info("6. Đánh giá chất lượng RAG Baseline (Hit Rate, Token F1, LLM Judge)...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    logger.info(f"   Baseline Hit Rate: {bundle.summary.get('retrieval_hit_rate', 0):.2%}")
    logger.info(f"   Mean Token F1: {bundle.summary.get('mean_token_f1', 0):.4f}")
    logger.info(f"   Judge Accuracy: {bundle.summary.get('judge_accuracy', 0):.2%}")

    # 7. Generate Phase 1 Markdown Report
    logger.info("7. Xuất báo cáo Markdown Phase 1...")
    source_summary = {
        "source_api": settings.source_api,
        "records_count": len(df),
        "query": settings.source_query,
        "filter": settings.source_filter,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    logger.info(f"   Báo cáo hoàn tất: {settings.paths.baseline_report}")
    logger.info("=== PHA 1 (BASELINE PIPELINE) HOÀN TẤT THÀNH CÔNG ===")


if __name__ == "__main__":
    main()
