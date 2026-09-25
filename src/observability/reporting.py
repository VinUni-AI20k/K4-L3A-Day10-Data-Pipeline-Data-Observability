from __future__ import annotations

from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase."""
    rows = [
        "# Baseline Pipeline Evaluation Report (Phase 1)",
        "",
        "## 1. Executive Summary",
        "",
        f"- **Quality Gate Status:** {'PASSED' if quality.get('success') else 'FAILED'}",
        f"- **Freshness SLA Status:** {'PASSED (Fresh)' if freshness.get('is_fresh') else 'FAILED (Stale)'}",
        f"- **Total Evaluated Documents:** {quality.get('evaluated_rows', 'N/A')}",
        "",
        "## 2. Data Source & Ingestion Summary",
        "",
    ]
    rows += [f"- **{k}:** {v}" for k, v in source_summary.items()]
    rows += [
        "",
        "## 3. Data Observability & Quality (Great Expectations 1.x)",
        "",
        f"- **Overall Success:** {quality.get('success', False)}",
        f"- **Total Expectations Evaluated:** {quality.get('total_expectations', 'N/A')}",
        f"- **Passed Expectations:** {quality.get('successful_expectations', 'N/A')}",
        f"- **Failed Expectations:** {quality.get('failed_expectations', 'N/A')}",
        "",
        "### Freshness SLA Metrics",
        f"- **Freshness SLA:** {freshness.get('is_fresh', False)}",
        f"- **Latest Published:** {freshness.get('latest_published', 'N/A')}",
        f"- **Oldest Published:** {freshness.get('oldest_published', 'N/A')}",
        f"- **Stale Rows Ratio:** {freshness.get('stale_ratio', 'N/A')} (Threshold: {freshness.get('freshness_threshold_days', 180)} days)",
        "",
        "## 4. Benchmark Retrieval & Answer Evaluation Metrics",
        "",
        "| Metric | Value | Description |",
        "|---|---:|---|",
    ]
    descriptions = {
        "samples": "Number of benchmark questions evaluated",
        "retrieval_hit_rate": "Ratio of questions where ground-truth document was retrieved in top-k",
        "mean_token_f1": "Mean token overlap F1 score between prediction and ground-truth",
        "judge_accuracy": "Ratio of answers marked materially correct by judge",
        "mean_judge_score": "Mean score given by judge (scale 1 - 5)",
    }
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        val = metrics.get(key, "N/A")
        val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
        desc = descriptions.get(key, "")
        rows.append(f"| {key} | {val_str} | {desc} |")

    rows.append("")
    write_text(report_path, "\n".join(rows) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    rows = [
        "# Corruption and Repair Comparison Report",
        "",
        "## Quantitative Comparison: 3-State Overview",
        "",
        "| Metric / Signal | Baseline (Clean) | Corrupted (Dirty) | Repaired (Recovered) |",
        "|---|---:|---:|---:|",
    ]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        b_val = f"{baseline_metrics[key]:.4f}" if isinstance(baseline_metrics.get(key), float) else str(baseline_metrics.get(key, "N/A"))
        c_val = f"{corrupted_metrics[key]:.4f}" if isinstance(corrupted_metrics.get(key), float) else str(corrupted_metrics.get(key, "N/A"))
        r_val = f"{repaired_metrics[key]:.4f}" if isinstance(repaired_metrics.get(key), float) else str(repaired_metrics.get(key, "N/A"))
        rows.append(f"| {key} | {b_val} | {c_val} | {r_val} |")

    rows += [
        f"| Quality Gate (GX 1.x) | True | {corrupted_quality.get('success', False)} | {repaired_quality.get('success', False)} |",
        f"| Freshness SLA (is_fresh) | True | {corrupted_freshness.get('is_fresh', False)} | {repaired_freshness.get('is_fresh', False)} |",
        f"| Stale Ratio | N/A | {corrupted_freshness.get('stale_ratio', 'N/A')} | {repaired_freshness.get('stale_ratio', 'N/A')} |",
        "",
        "## Quality Failures in Corrupted Data",
        "",
    ]
    for item in corrupted_quality.get("expectation_results", []):
        if not item.get("success", True):
            rows.append(f"- ❌ Violated Expectation: `{item.get('expectation_type', 'expectation')}`")
    rows.append("")
    write_text(report_path, "\n".join(rows) + "\n")

