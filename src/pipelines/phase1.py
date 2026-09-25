from datetime import datetime, timezone

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xay dung baseline pipeline end-to-end (Pha 4 / Checkpoint 3).

    1. Load settings & config.
    2. Fetch source records (co che dual-mode fallback).
    3. Clean raw records thanh dataframe.
    4. Luu clean CSV va JSON vao data/clean/.
    5. Build Chroma vector index 'papers-baseline'.
    6. Load hoac build bo benchmark test set (5 cau hoi).
    7. Evaluate baseline retrieval hit rate, token F1 va LLM judge.
    8. Chay chot kiem dich GX 1.x va Freshness SLA report.
    9. Xuat bao cao markdown vao data/reports/phase1_report.md.
    10. Smoke test demo agent voi cau hoi thuc te.
    """
    settings = load_settings()

    print("[1/6] Ingestion: Thu thap va bao toan du lieu tho...")
    raw_records = fetch_source_records(settings)
    source_summary = {
        "source_api": settings.source_api,
        "raw_count": len(raw_records),
    }

    print("[2/6] Cleaning: Chuan hoa, tinh age_days va tao text_for_embedding...")
    df = build_clean_dataframe(raw_records, now_utc())
    source_summary["clean_count"] = len(df)
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))

    print("[3/6] Indexing: Nap 24 tai lieu sach vao ChromaDB (papers-baseline)...")
    index = LocalEmbeddingIndex(settings, collection_name=settings.baseline_collection_name)
    index.build_from_clean()

    print("[4/6] Test Set & Evaluation: Danh gia Baseline...")
    load_or_create_test_set(df, settings.paths.eval_testset, force_refresh=settings.refresh_test_set)
    eval_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    print("[5/6] Observability: Kiem dinh Great Expectations 1.x & Freshness SLA...")
    quality = run_data_quality_checks(df, settings, "baseline")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    print("[6/6] Reporting: Xuat bao cao Markdown Pha 1...")
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=eval_bundle.summary,
        quality=quality,
        freshness=freshness,
    )

    # Demo agent best-effort
    try:
        agent = build_agent(settings, index)
        demo_q = "What is the summary of the paper 'Agentic Retrieval-Augmented Generation for Knowledge-Intensive Tasks'?"
        demo_ans = run_agent_question(agent, demo_q)
        write_json(settings.paths.demo_answers, [{"question": demo_q, "answer": demo_ans}])
    except Exception:
        pass

    print("\n" + "=" * 65)
    print(" ✅ PHASE 1 BASELINE PIPELINE HOÀN THÀNH XUẤT SẮC")
    print("=" * 65)
    print(f" • Dữ liệu sạch    : {len(df)} dòng -> {settings.paths.clean_csv}")
    print(f" • ChromaDB Index  : {settings.baseline_collection_name} ({len(index.documents)} docs)")
    print(f" • Test Set        : {len(eval_bundle.answers)} câu hỏi -> {settings.paths.eval_testset}")
    print(f" • Hit Rate        : {eval_bundle.summary['retrieval_hit_rate'] * 100:.1f}%")
    print(f" • Mean Token F1   : {eval_bundle.summary['mean_token_f1']:.4f}")
    print(f" • Judge Accuracy  : {eval_bundle.summary['judge_accuracy'] * 100:.1f}%")
    print(f" • GX 1.x Quality  : {'PASS (Thành công)' if quality.get('success') else 'FAIL'}")
    print(f" • Freshness SLA   : {'FRESH (Tươi mới)' if freshness.get('is_fresh') else 'STALE'}")
    print(f" • Báo cáo Pha 1   : {settings.paths.baseline_report}")
    print("=" * 65 + "\n")

