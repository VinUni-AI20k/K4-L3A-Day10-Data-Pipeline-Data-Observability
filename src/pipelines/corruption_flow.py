from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import load_settings, require_llm_credentials
from core.utils import now_utc, read_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.reporting import METRIC_ROWS, generate_corruption_report
from pipelines.common import index_and_evaluate, log, run_observability, save_clean_artifacts

# Columns that depend on the run date; excluded when checking that repair reproduces the baseline.
RUN_DEPENDENT_COLUMNS = {"age_days"}


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    require_llm_credentials(settings)

    # 1. Baseline state produced by phase 1.
    missing = [p for p in (paths.baseline_metrics, paths.clean_json, paths.eval_testset) if not p.exists()]
    if missing:
        raise SystemExit(f"Missing phase 1 artifacts {[p.name for p in missing]} — run `python script/run_phase1.py` first.")
    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_df = pd.read_json(paths.clean_json, dtype={"paper_id": str})
    log("baseline", f"{len(baseline_df)} clean rows, hit_rate={baseline_metrics['retrieval_hit_rate']:.4f}")

    # 2-3. Inject the 6 corruptions and persist corrupted artifacts.
    corrupted_df = corrupt_clean_dataframe(baseline_df.copy(), paths.corruption_log)
    save_clean_artifacts(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    log("corrupt", f"{len(baseline_df)} -> {len(corrupted_df)} rows, log -> {paths.corruption_log.name}")

    # 4. Observability on corrupted data: this is where the silent failure must become loud.
    corrupted_quality, corrupted_freshness = run_observability(
        corrupted_df,
        settings,
        "corrupted",
        paths.corrupted_quality_report,
        paths.quality_dir / "corrupted_freshness_report.json",
    )
    incident = not corrupted_quality.get("success") or not corrupted_freshness.get("is_fresh")
    if incident:
        log("alert", "DATA INCIDENT detected by quality gate / freshness SLA -> auto-repair will be triggered.")
    else:
        log("alert", "WARNING: corruption was NOT detected by observability (silent failure).")

    # 5. Simulation only: index the bad data anyway to measure what the agent would have served
    #    if the gate did not exist. In production the failed gate blocks this step.
    _, corrupted_metrics = index_and_evaluate(
        corrupted_df, settings, paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers
    )

    # 6. Idempotent repair: rebuild from the preserved raw snapshot, never patch corrupted rows.
    repaired_df = build_clean_dataframe(load_raw_records(paths.raw_records_json), now_utc())
    save_clean_artifacts(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)
    _check_repair_matches_baseline(baseline_df, repaired_df)

    repaired_quality, repaired_freshness = run_observability(
        repaired_df,
        settings,
        "repaired",
        paths.quality_dir / "repaired_quality_report.json",
        paths.quality_dir / "repaired_freshness_report.json",
    )
    if not repaired_quality.get("success"):
        raise SystemExit("Repaired data still fails the quality gate — refusing to serve it.")

    # 7. Evaluate repaired state on the same fixed test set.
    _, repaired_metrics = index_and_evaluate(
        repaired_df, settings, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers
    )

    # 8. Comparison report + console table.
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_metrics)
    log("report", f"-> {paths.comparison_report}")


def _check_repair_matches_baseline(baseline_df: pd.DataFrame, repaired_df: pd.DataFrame) -> None:
    """Idempotency proof: rebuilding from raw must reproduce the baseline content exactly."""
    columns = sorted((set(baseline_df.columns) & set(repaired_df.columns)) - RUN_DEPENDENT_COLUMNS)

    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        return df[columns].astype(str).sort_values("paper_id").reset_index(drop=True)

    if normalize(baseline_df).equals(normalize(repaired_df)):
        log("repair", f"idempotent: {len(repaired_df)} rows identical to baseline (ignoring {sorted(RUN_DEPENDENT_COLUMNS)})")
    else:
        log("repair", "WARNING: repaired data differs from baseline — check cleaning determinism.")


def _print_comparison(baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> None:
    header = f"{'Metric':<24}{'Baseline':>12}{'Corrupted':>12}{'Repaired':>12}"
    print("\n" + header + "\n" + "-" * len(header))
    for key, label in METRIC_ROWS:
        values = [state.get(key) for state in (baseline, corrupted, repaired)]
        print(f"{label:<24}" + "".join(f"{v:>12.4f}" if isinstance(v, (int, float)) else f"{'n/a':>12}" for v in values))
    print()

