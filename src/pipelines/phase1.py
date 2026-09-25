from __future__ import annotations

<<<<<<< HEAD
from datetime import UTC, datetime
import json

from core.config import load_settings
from core.utils import write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
=======
import logging

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import EvaluationBundle, evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
<<<<<<< HEAD
    """Run the clean baseline pipeline end to end.
=======
    """Build baseline pipeline end-to-end.
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)

    Steps:
    1. Load settings.
    2. Load or fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Create or load evaluation set.
    7. Evaluate.
    8. Run quality checks and freshness report.
    9. Create markdown report.
    10. Demo agent on sample questions.
    """
<<<<<<< HEAD
    settings = load_settings()
    print("[1/7] Loading source records...")
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)

    print("[2/7] Cleaning data...")
    clean_df = build_clean_dataframe(records, datetime.now(UTC))
    if clean_df.empty:
        raise RuntimeError("Cleaning produced no valid records")
    write_csv(clean_df, settings.paths.clean_csv)
    clean_payload = json.loads(clean_df.to_json(orient="records", date_format="iso"))
    write_json(settings.paths.clean_json, clean_payload)

    print("[3/7] Running Great Expectations quality gate...")
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    if not quality["success"]:
        raise RuntimeError(
            "Data quality gate failed; inspect "
            f"{settings.paths.baseline_quality_report} before indexing"
        )

    print("[4/7] Creating/loading benchmark test set...")
    test_set = load_or_create_test_set(clean_df, settings)

    print("[5/7] Building ChromaDB vector index...")
    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)

    print("[6/7] Evaluating baseline retrieval and QA...")
    evaluation = evaluate_pipeline(
=======
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

    # 1. Load settings
    logger.info("Loading settings...")
    settings = load_settings()
    for path in (
        settings.paths.clean_csv.parent,
        settings.paths.chroma_dir,
        settings.paths.eval_testset.parent,
        settings.paths.baseline_metrics.parent,
        settings.paths.baseline_report.parent,
        settings.paths.quality_dir,
        settings.paths.raw_records_json.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)
    logger.info("  LLM provider: %s, model: %s", settings.llm_provider, settings.model_name)
    logger.info("  Source API: %s", settings.source_api)

    run_date = now_utc()

    # 2. Load or fetch raw records
    logger.info("Fetching raw records from %s...", settings.source_api)
    raw_records = fetch_source_records(settings)
    logger.info("  Loaded %d raw records", len(raw_records))

    # 3. Clean data
    logger.info("Cleaning data...")
    df = build_clean_dataframe(raw_records, run_date)
    logger.info("  Clean records: %d", len(df))

    # 4. Save clean CSV/JSON
    logger.info("Saving clean data...")
    write_csv(df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    logger.info("  Saved to %s and %s", settings.paths.clean_csv, settings.paths.clean_json)

    # 5. Validate before indexing: bad data must not enter the vector store.
    logger.info("Running data quality checks...")
    quality = run_data_quality_checks(df, settings, report_name="baseline")
    freshness = quality.get("freshness", {})
    if not quality.get("gate_passed", quality.get("success", False)):
        raise RuntimeError("Baseline data quality gate failed; indexing was stopped.")

    # 6. Build Chroma index
    logger.info("Building Chroma index...")
    index = LocalEmbeddingIndex(settings, collection_name=settings.baseline_collection_name)
    count = index.build_from_clean()
    logger.info("  Indexed %d documents", count)

    # 7. Create or load evaluation set
    logger.info("Loading/creating evaluation test set...")
    test_set = load_or_create_test_set(df, settings.paths.eval_testset)
    logger.info("  Test set: %d samples", len(test_set.samples))

    # 8. Evaluate pipeline
    logger.info("Evaluating RAG pipeline...")
    bundle: EvaluationBundle = evaluate_pipeline(
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
<<<<<<< HEAD

    print("[7/7] Writing Phase 1 report...")
    source_summary = {
        "source": settings.source_api,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "indexed_documents": index.collection.count(),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        quality["freshness"],
    )

    print("\nPhase 1 baseline completed successfully.")
    print(f"Clean rows: {len(clean_df)}")
    print(f"Benchmark questions: {len(test_set)}")
    print(f"Indexed documents: {index.collection.count()}")
    print(f"Retrieval Hit Rate: {evaluation.summary['retrieval_hit_rate']:.4f}")
    print(f"Mean Token F1: {evaluation.summary['mean_token_f1']:.4f}")
    print(f"Report: {settings.paths.baseline_report}")
=======
    logger.info(
        "  Retrieval hit rate: %.2f%%, Token F1: %.3f, Judge accuracy: %.2f%%",
        bundle.summary["retrieval_hit_rate"] * 100,
        bundle.summary["mean_token_f1"],
        bundle.summary["judge_accuracy"] * 100,
    )

    logger.info("  Quality gate passed: %s, Fresh: %s", quality.get("gate_passed"), freshness.get("is_fresh"))

    # Build source summary
    source_summary = {
        "records_fetched": len(raw_records),
        "records_cleaned": len(df),
        "run_date": run_date.isoformat(),
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "max_results": settings.max_results,
    }

    # 9. Create markdown report
    logger.info("Generating phase 1 report...")
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    logger.info("  Report saved to %s", settings.paths.baseline_report)

    # 10. Optional agent demo. It is disabled by default so offline baseline
    # runs do not require an LLM key or a running Ollama server.
    import os
    if os.getenv("RUN_AGENT_DEMO", "").lower() not in {"1", "true", "yes"}:
        logger.info("Agent demo skipped (set RUN_AGENT_DEMO=1 to enable).")
        return
    logger.info("Running agent demo...")
    agent = build_agent(settings, index)

    sample_questions = [
        "What papers about agentic retrieval are available?",
        "Find information about 'Adaptive RAG' if it exists.",
    ]

    demo_answers = []
    for question in sample_questions:
        logger.info("  Question: %s", question)
        answer = run_agent_question(agent, question)
        logger.info("  Answer: %s", answer[:200] + "..." if len(answer) > 200 else answer)
        demo_answers.append({"question": question, "answer": answer})

    write_json(settings.paths.demo_answers, demo_answers)
    logger.info("Demo complete. Pipeline finished successfully.")


if __name__ == "__main__":
    main()
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
