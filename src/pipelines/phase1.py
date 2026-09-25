from __future__ import annotations

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTIONS = [
    "Which indexed papers discuss agentic retrieval augmented generation?",
    "Summarise what the corpus says about evaluating RAG pipelines.",
]


def save_clean_dataset(df, settings: Settings) -> None:
    """Luu dataframe sach ra ca CSV (de doc bang mat) va JSON (giu nguyen kieu list)."""
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))


def run_agent_demo(settings: Settings, index: LocalEmbeddingIndex) -> None:
    """Demo QA Agent tren vai cau hoi. Loi LLM khong duoc lam sap pipeline."""
    try:
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        answers = [
            {"question": question, "answer": run_agent_question(agent, question)}
            for question in DEMO_QUESTIONS
        ]
        write_json(settings.paths.demo_answers, answers)
        print(f"[demo] Da ghi {len(answers)} cau tra loi cua agent vao {settings.paths.demo_answers}")
    except Exception as exc:  # noqa: BLE001
        print(f"[demo] Bo qua agent demo (LLM khong san sang): {exc}")


def main() -> None:
    settings = load_settings()
    run_date = now_utc()
    print("=" * 72)
    print("PHASE 1 - BASELINE DATA PIPELINE (CP0 -> CP3)")
    print("=" * 72)

    # --- 1. Raw ingestion & lineage ---
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)
    print(f"[1/7] Raw ingestion: {len(records)} ban ghi tu {settings.source_api}")

    # --- 2. Cleaning & data modeling ---
    clean_df = build_clean_dataframe(records, run_date)
    save_clean_dataset(clean_df, settings)
    print(f"[2/7] Cleaning: {len(clean_df)} dong sach -> {settings.paths.clean_csv}")

    # --- 3. Data Quality Gate (GX 1.x) + Freshness SLA ---
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"[3/7] Quality Gate: success={quality['success']} | Freshness: is_fresh={freshness['is_fresh']}")
    if not quality["success"]:
        print("      [!] Quality Gate FAIL - du lieu xau se khong duoc phep vao Vector Store o production.")

    # --- 4. Embedding & Chroma index ---
    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    print(f"[4/7] Index: collection '{index.collection_name}' voi {len(index.documents)} tai lieu")

    # --- 5. Test set ---
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)
    print(f"[5/7] Test set: {len(test_set)} cau hoi -> {settings.paths.eval_testset}")

    # --- 6. Baseline evaluation ---
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    metrics = bundle.summary
    print(
        f"[6/7] Baseline metrics: hit_rate={metrics['retrieval_hit_rate']:.4f} "
        f"| token_f1={metrics['mean_token_f1']:.4f} | judge={metrics['mean_judge_score']:.2f}"
    )

    # --- 7. Markdown report ---
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_api_response": str(settings.paths.raw_api_response),
        "raw_records_json": str(settings.paths.raw_records_json),
        "raw_records": len(records),
        "clean_rows": int(len(clean_df)),
        "embedding_model": settings.embedding_model,
        "collection_name": index.collection_name,
        "top_k": settings.top_k,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.model_name,
        "run_date": run_date.isoformat(),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=metrics,
        quality=quality,
        freshness=freshness,
    )
    print(f"[7/7] Report: {settings.paths.baseline_report}")

    run_agent_demo(settings, index)
    print("-" * 72)
    print("PHASE 1 HOAN TAT.")
