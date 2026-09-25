from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import ensure_parent, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from observability.quality import build_freshness_report, run_data_quality_checks
from retrieval.index import LocalEmbeddingIndex


def log(step: str, message: str) -> None:
    print(f"[{step}] {message}", flush=True)


def save_clean_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    # orient="records" so `pd.read_json(json_path)` round-trips (used by the checkpoint checks);
    # pandas handles datetime/NaN values that json.dumps would reject.
    ensure_parent(json_path)
    df.to_json(json_path, orient="records", indent=2, date_format="iso", force_ascii=True)


def run_observability(
    df: pd.DataFrame,
    settings: Settings,
    report_name: str,
    quality_report_path: Path,
    freshness_report_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = run_data_quality_checks(df, settings, report_name)
    write_json(quality_report_path, quality)
    freshness = build_freshness_report(df, settings, freshness_report_path)
    log("quality", f"{report_name}: gate success={quality.get('success')} | is_fresh={freshness.get('is_fresh')}")
    return quality, freshness


def index_and_evaluate(
    df: pd.DataFrame,
    settings: Settings,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
) -> tuple[LocalEmbeddingIndex, dict[str, Any]]:
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    log("index", f"collection '{index.collection_name}' <- {len(index.documents)} documents")
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path)
    summary = bundle.summary
    log(
        "eval",
        f"{index.collection_name}: hit_rate={summary['retrieval_hit_rate']:.4f} "
        f"token_f1={summary['mean_token_f1']:.4f} judge_acc={summary['judge_accuracy']:.4f}",
    )
    return index, summary
