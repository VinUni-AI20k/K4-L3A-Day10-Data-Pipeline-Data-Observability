from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings
from core.utils import now_utc, write_dataframe, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


DEMO_QUESTION_COUNT = 2


def _load_or_fetch_raw(settings: Settings) -> tuple[list[PaperRecord], str]:
    """Tang 1 - Raw Preservation: uu tien doc ban raw da luu, chi fetch khi can."""
    paths = settings.paths
    if settings.refresh_source or not paths.raw_records_json.exists():
        return fetch_source_records(settings), "fetched (live API or offline snapshot fallback)"
    return load_raw_records(paths.raw_records_json), f"loaded from {paths.raw_records_json.name}"


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, questions: list[str]) -> list[dict[str, Any]]:
    """Demo QA Agent tren vai cau hoi. Loi provider (thieu key, mock...) khong lam dung pipeline."""
    from retrieval.agent import build_agent, run_agent_question

    try:
        agent = build_agent(settings, index)
    except Exception as exc:
        return [{"question": question, "error": f"Agent unavailable: {exc}"} for question in questions]

    answers: list[dict[str, Any]] = []
    for question in questions:
        try:
            answers.append({"question": question, "answer": run_agent_question(agent, question)})
        except Exception as exc:
            answers.append({"question": question, "error": f"Agent failed: {exc}"})
    return answers


def main() -> None:
    """Baseline pipeline end-to-end tren du lieu sach.

    raw -> clean -> quality gate -> test set -> ChromaDB -> evaluate -> report
    """
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    # 1-2. Raw ingestion
    records, raw_mode = _load_or_fetch_raw(settings)
    print(f"[phase1] Raw: {len(records)} records ({raw_mode})")

    # 3-4. Cleaning + luu clean artifacts
    clean_df = build_clean_dataframe(records, run_date)
    write_dataframe(clean_df, paths.clean_csv, paths.clean_json)
    print(f"[phase1] Clean: {len(clean_df)} rows -> {paths.clean_csv.name}, {paths.clean_json.name}")

    # 5. Quality Gate chay TRUOC khi index: du lieu xau khong duoc lot vao Vector Store
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)
    print(f"[phase1] Quality Gate: success={quality['success']} | Freshness: is_fresh={freshness['is_fresh']}")
    if not quality["success"]:
        raise RuntimeError(
            "Quality Gate failed on baseline data - pipeline stopped before indexing. "
            f"See {paths.baseline_quality_report}."
        )

    # 6. Test set co dinh: chi sinh lan dau (hoac REFRESH_TEST_SET=1) de moi lan do deu cung de thi
    if settings.refresh_test_set or not paths.eval_testset.exists():
        test_set = build_test_set(clean_df, paths.eval_testset)
        print(f"[phase1] Test set: generated {len(test_set)} questions -> {paths.eval_testset.name}")
    else:
        print(f"[phase1] Test set: reusing fixed benchmark {paths.eval_testset.name}")

    # 7. Vector index (collection papers-baseline)
    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)
    print(f"[phase1] Index: {len(index.documents)} docs -> Chroma collection '{index.collection_name}'")

    # 8. Evaluate baseline
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics,
        answers_output_path=paths.baseline_answers,
    )
    metrics = bundle.summary

    # 9. Demo QA Agent (multi-provider)
    demo_questions = [answer["question"] for answer in bundle.answers[:DEMO_QUESTION_COUNT]]
    write_json(paths.demo_answers, _run_agent_demo(settings, index, demo_questions))

    # 10. Markdown report
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_mode": raw_mode,
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "run_date": run_date.isoformat(),
        "embedding_model": settings.embedding_model,
        "collection_name": index.collection_name,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.model_name,
    }
    generate_phase1_report(paths.baseline_report, source_summary, metrics, quality, freshness)

    print(
        "[phase1] Baseline metrics: "
        f"hit_rate={metrics['retrieval_hit_rate']:.3f} | "
        f"token_f1={metrics['mean_token_f1']:.3f} | "
        f"judge_accuracy={metrics['judge_accuracy']:.3f}"
    )
    print(f"[phase1] Done. Report -> {paths.baseline_report}")
