from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def main() -> None:
    settings = load_settings()

    print("[1/8] Loading raw source records (Crossref)...")
    records = fetch_source_records(settings)
    print(f"      -> {len(records)} raw records available.")

    print("[2/8] Cleaning & normalizing records...")
    run_date = now_utc()
    clean_df = build_clean_dataframe(records, run_date)
    if clean_df.empty:
        raise RuntimeError("Cleaning produced zero valid records; aborting baseline pipeline.")
    print(f"      -> {len(clean_df)} clean records kept.")

    print("[3/8] Writing clean artifacts...")
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    print("[4/8] Running data quality gate (Great Expectations 1.x) + freshness check...")
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    print(f"      -> quality gate success={quality['success']}")
    if not quality["success"]:
        print("      WARNING: baseline data did not pass the quality gate. Continuing pipeline, see report.")

    print("[5/8] Building MiniLM embeddings & ChromaDB baseline index...")
    index = LocalEmbeddingIndex.build(clean_df, settings, embeddings_output_path=settings.paths.embeddings_json)
    print(f"      -> collection '{index.collection_name}' populated with {len(index.documents)} documents.")

    print("[6/8] Preparing evaluation test set...")
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
        print(f"      -> generated {len(test_set)} benchmark questions.")
    else:
        test_set = read_json(settings.paths.eval_testset)
        print(f"      -> reused existing test set with {len(test_set)} questions.")

    print("[7/8] Evaluating baseline pipeline (Hit Rate, Token F1, LLM Judge)...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(
        "      -> hit_rate=%.4f token_f1=%.4f judge_accuracy=%.4f"
        % (
            bundle.summary["retrieval_hit_rate"],
            bundle.summary["mean_token_f1"],
            bundle.summary["judge_accuracy"],
        )
    )

    print("[8/8] Writing Phase 1 markdown report...")
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "raw_record_count": len(records),
        "clean_record_count": len(clean_df),
        "embedding_model": settings.embedding_model,
        "vector_collection": index.collection_name,
        "top_k": settings.top_k,
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=quality["freshness"],
    )

    print("      -> demo: answering a couple of sample questions with the baseline retriever...")
    for sample in test_set[:2]:
        try:
            result = answer_question(sample["question"], settings=settings, index=index)
            print(f"         Q: {result.question}\n         A: {result.answer}")
        except Exception as exc:  # pragma: no cover - demo is best-effort
            print(f"         Demo answer skipped ({exc}).")

    print("\nPhase 1 baseline pipeline complete.")
    print(f"  clean data     -> {settings.paths.clean_csv}")
    print(f"  chroma index   -> {settings.paths.chroma_dir}")
    print(f"  test set       -> {settings.paths.eval_testset}")
    print(f"  baseline metrics -> {settings.paths.baseline_metrics}")
    print(f"  report         -> {settings.paths.baseline_report}")


if __name__ == "__main__":
    main()
