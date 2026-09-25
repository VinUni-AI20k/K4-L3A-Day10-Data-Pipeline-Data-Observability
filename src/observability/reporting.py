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
    lines = ["# Phase 1 Baseline Report", "", "## Source", ""]
    lines.extend(f"- **{key}:** {value}" for key, value in source_summary.items())
    lines.extend(["", "## Metrics", ""])
    lines.extend(f"- **{key}:** {value}" for key, value in metrics.items())
    lines.extend(["", "## Quality", "", f"- **Success:** {quality['success']}", f"- **Checks:** {quality['checks']}"])
    lines.extend(["", "## Freshness", "", f"- **Fresh:** {freshness['is_fresh']}", f"- **Stale rows:** {freshness['stale_rows']}/{freshness['total_rows']}", ""])
    write_text(report_path, "\n".join(lines))


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
    metric_names = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]
    lines = ["# Corruption and Repair Report", "", "| Metric | Baseline | Corrupted | Repaired |", "|---|---:|---:|---:|"]
    lines.extend(f"| {name} | {baseline_metrics.get(name)} | {corrupted_metrics.get(name)} | {repaired_metrics.get(name)} |" for name in metric_names)
    lines.extend(["", "## Quality and Freshness", "", f"- Corrupted quality gate: `{corrupted_quality['success']}`", f"- Repaired quality gate: `{repaired_quality['success']}`", f"- Corrupted freshness: `{corrupted_freshness['is_fresh']}`", f"- Repaired freshness: `{repaired_freshness['is_fresh']}`", ""])
    write_text(report_path, "\n".join(lines))
