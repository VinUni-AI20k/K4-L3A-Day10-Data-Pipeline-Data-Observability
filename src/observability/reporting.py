from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


def _status_badge(success: bool) -> str:
    return "PASS" if success else "FAIL"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the Phase 1 baseline markdown report."""

    lines: list[str] = []
    lines.append("# Phase 1 Baseline Report")
    lines.append("")
    lines.append(f"Generated: {now_utc().isoformat()}")
    lines.append("")

    lines.append("## Data Source Summary")
    lines.append("")
    for key, value in source_summary.items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.append("## Retrieval & Evaluation Metrics")
    lines.append("")
    lines.append(f"- **Samples evaluated**: {metrics.get('samples')}")
    lines.append(f"- **Retrieval Hit Rate**: {metrics.get('retrieval_hit_rate'):.4f}")
    lines.append(f"- **Mean Token F1**: {metrics.get('mean_token_f1'):.4f}")
    lines.append(f"- **LLM Judge Accuracy**: {metrics.get('judge_accuracy'):.4f}")
    lines.append(f"- **Mean LLM Judge Score**: {metrics.get('mean_judge_score'):.4f} / 5")
    ragas = metrics.get("ragas")
    if isinstance(ragas, dict):
        if "skipped" in ragas:
            lines.append(f"- **Ragas**: skipped ({ragas['skipped']})")
        elif "error" in ragas:
            lines.append(f"- **Ragas**: error ({ragas['error']})")
        else:
            for name, value in ragas.items():
                lines.append(f"- **Ragas {name}**: {value}")
    lines.append("")

    lines.append("## Data Quality Gate (Great Expectations 1.x)")
    lines.append("")
    lines.append(f"- **Overall status**: {_status_badge(bool(quality.get('success')))}")
    lines.append(f"- **GX expectations status**: {_status_badge(bool(quality.get('gx_success')))}")
    lines.append(f"- **Row count**: {quality.get('row_count')}")
    missing_columns = quality.get("missing_columns") or []
    if missing_columns:
        lines.append(f"- **Missing columns**: {', '.join(missing_columns)}")
    lines.append("")
    lines.append("| Expectation | Result |")
    lines.append("| :--- | :--- |")
    for expectation in quality.get("expectations", []):
        lines.append(f"| {expectation.get('name')} | {_status_badge(bool(expectation.get('success')))} |")
    lines.append("")

    lines.append("## Freshness Check")
    lines.append("")
    lines.append(f"- **Status**: {_status_badge(bool(freshness.get('is_fresh')))}")
    lines.append(f"- **Latest published**: {freshness.get('latest_published')}")
    lines.append(f"- **Oldest published**: {freshness.get('oldest_published')}")
    lines.append(
        f"- **Stale rows**: {freshness.get('stale_rows')} / {freshness.get('total_rows')} "
        f"({freshness.get('stale_ratio', 0.0):.2%})"
    )
    lines.append(f"- **Freshness threshold**: {freshness.get('freshness_threshold_days')} days")
    lines.append(f"- **Max allowed stale ratio**: {freshness.get('max_stale_ratio', 0.0):.2%}")
    lines.append("")

    write_text(report_path, "\n".join(lines) + "\n")


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
    raise NotImplementedError("Student task: implement corruption comparison report.")
