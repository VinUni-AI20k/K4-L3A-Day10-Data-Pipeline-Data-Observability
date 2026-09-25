from __future__ import annotations

from core.config import load_settings, normalized_provider, require_llm_credentials
from core.utils import now_utc, read_json, write_json
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.reporting import generate_phase1_report
from pipelines.common import index_and_evaluate, log, run_observability, save_clean_artifacts

DEMO_QUESTION_COUNT = 2


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    require_llm_credentials(settings)
    log("setup", f"LLM provider={settings.llm_provider} model={settings.model_name}")

    # 1-2. Raw ingestion: reuse the preserved raw snapshot unless a refresh is requested.
    if settings.refresh_source or not paths.raw_records_json.exists():
        records = fetch_source_records(settings)
        source_mode = "fetched (Crossref API / snapshot fallback)"
    else:
        records = load_raw_records(paths.raw_records_json)
        source_mode = "loaded from raw snapshot"
    log("ingest", f"{len(records)} records {source_mode}")

    # 3-4. Clean + persist.
    run_date = now_utc()
    df = build_clean_dataframe(records, run_date)
    save_clean_artifacts(df, paths.clean_csv, paths.clean_json)
    log("clean", f"{len(df)} clean rows -> {paths.clean_csv.name}, {paths.clean_json.name}")

    # 5. Quality gate BEFORE indexing: bad data must never reach the vector store.
    quality, freshness = run_observability(
        df, settings, "baseline", paths.baseline_quality_report, paths.freshness_report
    )
    if not quality.get("success"):
        raise SystemExit(
            f"Quality gate FAILED on baseline data — refusing to index. See {paths.baseline_quality_report}"
        )
    if not freshness.get("is_fresh"):
        log("quality", "WARNING: freshness SLA breached — corpus needs a refresh (indexing continues).")

    # 6. Fixed benchmark: reuse existing test set so all 3 states are scored on identical questions.
    if settings.refresh_test_set or not paths.eval_testset.exists():
        test_set = build_test_set(df, paths.eval_testset)
        log("testset", f"built {len(test_set)} questions -> {paths.eval_testset.name}")
    else:
        log("testset", f"reusing existing {paths.eval_testset.name}")

    # 7-8. Index into Chroma (papers-baseline) + evaluate.
    index, metrics = index_and_evaluate(
        df, settings, paths.embeddings_json, paths.baseline_metrics, paths.baseline_answers
    )

    # 9. Markdown report.
    source_summary = {
        "source_api": settings.source_api,
        "source_mode": source_mode,
        "run_date": run_date.isoformat(timespec="seconds"),
        "raw_records": len(records),
        "clean_rows": len(df),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "llm_provider": settings.llm_provider,
    }
    generate_phase1_report(paths.baseline_report, source_summary, metrics, quality, freshness)
    log("report", f"-> {paths.baseline_report}")

    # 10. Optional agent demo (the mock LLM cannot call tools, so skip it there).
    if normalized_provider(settings) != "mock":
        _run_agent_demo(settings, index)
    log("done", "Phase 1 baseline pipeline completed.")


def _run_agent_demo(settings, index) -> None:
    from retrieval.agent import build_agent, run_agent_question

    try:
        agent = build_agent(settings, index)
        questions = [item["question"] for item in read_json(settings.paths.eval_testset)[:DEMO_QUESTION_COUNT]]
        demo = [{"question": q, "answer": run_agent_question(agent, q)} for q in questions]
        write_json(settings.paths.demo_answers, demo)
        log("agent", f"demo answers -> {settings.paths.demo_answers.name}")
    except Exception as exc:  # demo is non-critical; never fail the pipeline on it
        log("agent", f"demo skipped: {exc}")
