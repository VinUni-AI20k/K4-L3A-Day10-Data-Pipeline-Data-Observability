from __future__ import annotations


from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def main() -> None:
    """Xay dung baseline pipeline end-to-end."""
    print("=== BAT DAU BASELINE PIPELINE (PHASE 1) ===")
    settings = load_settings()

    # 1. Fetch / Load raw records
    records = fetch_source_records(settings)
    print(f"[1/8] Da tai thanh cong {len(records)} raw records tu {settings.source_api}.")

    # 2. Clean data
    clean_df = build_clean_dataframe(records, now_utc())
    print(f"[2/8] Clean thanh cong {len(clean_df)} dong du lieu.")

    # 3. Save clean CSV & JSON
    write_csv(clean_df, settings.paths.clean_csv)
    clean_df.to_json(settings.paths.clean_json, orient="records", indent=2)
    print(f"[3/8] Da luu cleaned dataset vao {settings.paths.clean_csv} va {settings.paths.clean_json}.")

    # 4. Build Chroma index
    index = LocalEmbeddingIndex.build(clean_df, settings)
    print(f"[4/8] Da build Chroma index thanh cong ({index.collection.count()} docs trong {index.collection_name}).")

    # 5. Build or load test set
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)
    print(f"[5/8] Test set san sang voi {len(test_set)} cau hoi.")

    # 6. Evaluate baseline pipeline
    print("[6/8] Dang danh gia baseline pipeline tren test set...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(f"      Hit Rate: {bundle.summary['retrieval_hit_rate']:.4f} | Token F1: {bundle.summary['mean_token_f1']:.4f}")

    # 7. Run Data Quality Checks & Freshness SLA
    print("[7/8] Dang chay kiem tra chat luong du lieu (GX 1.x) va Freshness SLA...")
    quality_res = run_data_quality_checks(clean_df, settings, "baseline")
    freshness_res = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"      Quality Gate Success: {quality_res['success']} | Freshness SLA: {freshness_res['is_fresh']}")

    # 8. Generate Phase 1 Markdown Report
    source_summary = {
        "Source API": settings.source_api,
        "Search Query": settings.source_query,
        "Total Raw Records": len(records),
        "Total Clean Rows": len(clean_df),
        "Collection Name": index.collection_name,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality_res,
        freshness=freshness_res,
    )
    print(f"[8/8] Da xuat bao cao Phase 1 tai: {settings.paths.baseline_report}")

    # 9. Demo QA Agent on 1 question
    if test_set:
        demo_question = test_set[0]["question"]
        demo_res = answer_question(demo_question, settings=settings, index=index)
        write_json(
            settings.paths.demo_answers,
            [
                {
                    "question": demo_question,
                    "answer": demo_res.answer,
                    "retrieved_doc_ids": demo_res.retrieved_doc_ids,
                    "retrieved_titles": demo_res.retrieved_titles,
                }
            ],
        )

    print("=== BASELINE PIPELINE (PHASE 1) HOAN THANH XUAT SAC! ===")

