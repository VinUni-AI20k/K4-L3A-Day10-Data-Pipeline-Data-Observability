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
    """TODO(student): viet markdown report cho baseline phase.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    rows = ["# Baseline evaluation", "", "## Source", ""]
    rows += [f"- {k}: {v}" for k, v in source_summary.items()]
    rows += ["", "## Metrics", "", "| Metric | Value |", "|---|---:|"]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        rows.append(f"| {key} | {metrics.get(key, 'N/A')} |")
    rows += ["", f"- Quality Gate: {quality.get('success', False)}",
             f"- Freshness: {freshness.get('is_fresh', False)}",
             f"- Stale ratio: {freshness.get('stale_ratio', 'N/A')}", ""]
    write_text(report_path, "\n".join(rows))


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
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    rows = ["# Corruption and repair comparison", "",
            "| Metric | Baseline | Corrupted | Repaired |", "|---|---:|---:|---:|"]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        rows.append(f"| {key} | {baseline_metrics.get(key, 'N/A')} | {corrupted_metrics.get(key, 'N/A')} | {repaired_metrics.get(key, 'N/A')} |")
    rows += [f"| Quality Gate | N/A | {corrupted_quality.get('success', False)} | {repaired_quality.get('success', False)} |",
             f"| Freshness | N/A | {corrupted_freshness.get('is_fresh', False)} | {repaired_freshness.get('is_fresh', False)} |", "",
             "## Quality failures in corrupted data", ""]
    for item in corrupted_quality.get("results", []):
        if not item.get("success", True):
            rows.append(f"- {item.get('expectation_config', {}).get('type', 'expectation')}")
    write_text(report_path, "\n".join(rows) + "\n")
