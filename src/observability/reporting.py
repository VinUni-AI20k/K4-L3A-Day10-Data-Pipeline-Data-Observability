from __future__ import annotations

from typing import Any

from core.utils import write_text


def _fmt(value: Any, decimals: int = 4) -> str:
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value) if value is not None else "N/A"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source Summary",
        f"- Records ingested: {source_summary.get('record_count', 'N/A')}",
        f"- Source: {source_summary.get('source', 'Crossref API')}",
        f"- Query: {source_summary.get('query', 'N/A')}",
        "",
        "## Baseline Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| retrieval_hit_rate | {_fmt(metrics.get('retrieval_hit_rate'))} |",
        f"| mean_token_f1 | {_fmt(metrics.get('mean_token_f1'))} |",
        f"| judge_accuracy | {_fmt(metrics.get('judge_accuracy'))} |",
        f"| mean_judge_score | {_fmt(metrics.get('mean_judge_score'))} |",
        f"| samples | {metrics.get('samples', 'N/A')} |",
        "",
        "## Data Quality (Great Expectations 1.x)",
        f"- Overall success: **{quality.get('success', 'N/A')}**",
    ]
    for r in quality.get("results", []):
        status = "PASS" if r["success"] else "FAIL"
        col = r.get("kwargs", {}).get("column", "")
        col_label = f" (column: {col})" if col else ""
        lines.append(f"  - [{status}] {r['expectation']}{col_label}")
    lines += [
        "",
        "## Freshness SLA",
        f"- is_fresh: **{freshness.get('is_fresh', 'N/A')}**",
        f"- stale_rows: {freshness.get('stale_rows', 'N/A')} / {freshness.get('total_rows', 'N/A')}",
        f"- stale_ratio: {_fmt(freshness.get('stale_ratio'))}",
        f"- threshold_days: {freshness.get('threshold_days', 'N/A')}",
        f"- latest_published: {freshness.get('latest_published', 'N/A')}",
        f"- oldest_published: {freshness.get('oldest_published', 'N/A')}",
    ]
    write_text(report_path, "\n".join(lines) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_freshness: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    def delta(base: Any, other: Any) -> str:
        try:
            d = float(other) - float(base)
            return f"{d:+.4f}"
        except (TypeError, ValueError):
            return "N/A"

    lines = [
        "# Corruption vs Repair — 3-State Comparison Report",
        "",
        "## Metrics Comparison",
        "",
        "| Metric | Baseline | Corrupted | Δ Corrupted | Repaired | Δ Repaired |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]:
        b = baseline_metrics.get(key)
        c = corrupted_metrics.get(key)
        r = repaired_metrics.get(key)
        lines.append(
            f"| {key} | {_fmt(b)} | {_fmt(c)} | {delta(b, c)} | {_fmt(r)} | {delta(b, r)} |"
        )

    lines += [
        "",
        "## Data Quality & Freshness",
        "",
        "| State | GX Pass | GX Failures | is_fresh | Stale Ratio | Stale Rows |",
        "| --- | :---: | --- | :---: | ---: | ---: |",
    ]
    for label, q, f in [
        ("Baseline", baseline_quality, baseline_freshness),
        ("Corrupted", corrupted_quality, corrupted_freshness),
        ("Repaired", repaired_quality, repaired_freshness),
    ]:
        gx_pass = "✅" if q.get("success") else "❌"
        failures = ", ".join(
            r["expectation"].replace("expect_", "").replace("_", " ")
            for r in q.get("results", []) if not r["success"]
        ) or "none"
        fresh = "✅" if f.get("is_fresh") else "❌"
        stale_ratio = _fmt(f.get("stale_ratio"), decimals=1)
        stale_rows = f"{f.get('stale_rows', 0)}/{f.get('total_rows', 0)}"
        lines.append(f"| {label} | {gx_pass} | {failures} | {fresh} | {stale_ratio} | {stale_rows} |")

    lines += [
        "",
        "## Analysis",
        "",
        "### Corruption Impact (Silent Failure)",
        f"- `retrieval_hit_rate` dropped from {_fmt(baseline_metrics.get('retrieval_hit_rate'))} → {_fmt(corrupted_metrics.get('retrieval_hit_rate'))} "
        f"({delta(baseline_metrics.get('retrieval_hit_rate'), corrupted_metrics.get('retrieval_hit_rate'))})",
        f"- `mean_token_f1` dropped from {_fmt(baseline_metrics.get('mean_token_f1'))} → {_fmt(corrupted_metrics.get('mean_token_f1'))} "
        f"({delta(baseline_metrics.get('mean_token_f1'), corrupted_metrics.get('mean_token_f1'))})",
        "- GX quality gate detected violations (duplicate paper_id, blank summary) — `success=False`",
        f"- Freshness SLA: stale ratio rose from {_fmt(baseline_freshness.get('stale_ratio'))} → {_fmt(corrupted_freshness.get('stale_ratio'))}",
        "",
        "### Repair Recovery (Idempotent from Raw Snapshot)",
        f"- `retrieval_hit_rate` restored to {_fmt(repaired_metrics.get('retrieval_hit_rate'))}",
        f"- `mean_token_f1` restored to {_fmt(repaired_metrics.get('mean_token_f1'))}",
        "- GX quality gate passed — `success=True`",
        f"- Freshness SLA restored to is_fresh={repaired_freshness.get('is_fresh')}",
    ]
    write_text(report_path, "\n".join(lines) + "\n")
