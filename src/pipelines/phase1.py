from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xay dung baseline pipeline end-to-end.

    Pseudo-code:
    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Co the demo agent tren vai sample question.
    """
    settings = load_settings()
    paths = settings.paths

    if settings.refresh_source or not paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(paths.raw_records_json)

    df = build_clean_dataframe(records, now_utc())
    write_csv(df, paths.clean_csv)
    write_json(paths.clean_json, df.to_dict(orient="records"))

    quality = run_data_quality_checks(df, settings, "baseline_quality_report")
    freshness = build_freshness_report(df, settings, paths.freshness_report)

    index = LocalEmbeddingIndex.build(df, settings, paths.embeddings_json)
    load_or_create_test_set(df, paths.eval_testset, force_refresh=settings.refresh_test_set)
    bundle = evaluate_pipeline(settings, index, paths.eval_testset, paths.baseline_metrics, paths.baseline_answers)

    source_summary = {
        "api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "records": len(records),
        "clean_rows": len(df),
    }
    generate_phase1_report(paths.baseline_report, source_summary, bundle.summary, quality, freshness)
    print(f"Phase 1 done: hit_rate={bundle.summary['retrieval_hit_rate']:.2f}, "
          f"token_f1={bundle.summary['mean_token_f1']:.3f}. Report: {paths.baseline_report}")
