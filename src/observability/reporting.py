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


def _quality_cell(quality: dict[str, Any]) -> str:
    success = bool(quality.get("success"))
    row_count = quality.get("row_count")
    return f"{_status_badge(success)} (rows={row_count})"


def _freshness_cell(freshness: dict[str, Any]) -> str:
    is_fresh = bool(freshness.get("is_fresh"))
    stale_ratio = freshness.get("stale_ratio", 0.0)
    return f"{_status_badge(is_fresh)} (stale={stale_ratio:.2%})"


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
    """Write the 3-state (baseline/corrupted/repaired) comparison markdown report."""

    def metric(bundle: dict[str, Any], key: str) -> float:
        return float(bundle.get(key) or 0.0)

    lines: list[str] = []
    lines.append("# Corruption, Repair & Comparison Report")
    lines.append("")
    lines.append(f"Generated: {now_utc().isoformat()}")
    lines.append("")

    lines.append("## Bang Doi Chieu 3 Trang Thai")
    lines.append("")
    lines.append("| Metric | Baseline (Sach) | Corrupted (Loi) | Repaired (Phuc hoi) |")
    lines.append("| :--- | :--- | :--- | :--- |")
    lines.append(
        "| Data Quality Gate | "
        f"{_quality_cell(baseline_quality)} | {_quality_cell(corrupted_quality)} | {_quality_cell(repaired_quality)} |"
    )
    lines.append(
        "| Freshness Check | "
        f"{_freshness_cell(baseline_freshness)} | {_freshness_cell(corrupted_freshness)} | {_freshness_cell(repaired_freshness)} |"
    )
    lines.append(
        "| Retrieval Hit Rate | "
        f"{metric(baseline_metrics, 'retrieval_hit_rate'):.4f} | "
        f"{metric(corrupted_metrics, 'retrieval_hit_rate'):.4f} | "
        f"{metric(repaired_metrics, 'retrieval_hit_rate'):.4f} |"
    )
    lines.append(
        "| Mean Token F1 | "
        f"{metric(baseline_metrics, 'mean_token_f1'):.4f} | "
        f"{metric(corrupted_metrics, 'mean_token_f1'):.4f} | "
        f"{metric(repaired_metrics, 'mean_token_f1'):.4f} |"
    )
    lines.append(
        "| LLM Judge Accuracy | "
        f"{metric(baseline_metrics, 'judge_accuracy'):.4f} | "
        f"{metric(corrupted_metrics, 'judge_accuracy'):.4f} | "
        f"{metric(repaired_metrics, 'judge_accuracy'):.4f} |"
    )
    lines.append("")

    hit_rate_drop = metric(baseline_metrics, "retrieval_hit_rate") - metric(corrupted_metrics, "retrieval_hit_rate")
    f1_drop = metric(baseline_metrics, "mean_token_f1") - metric(corrupted_metrics, "mean_token_f1")
    hit_rate_recovered = metric(repaired_metrics, "retrieval_hit_rate") >= metric(baseline_metrics, "retrieval_hit_rate")
    f1_recovered = metric(repaired_metrics, "mean_token_f1") >= metric(baseline_metrics, "mean_token_f1") - 1e-6

    lines.append("## Phan Tich Suy Giam & Phuc Hoi")
    lines.append("")
    lines.append(
        f"- **Data Corruption gay sut giam Hit Rate**: {hit_rate_drop:+.4f} "
        f"({'silent failure phat hien' if hit_rate_drop > 0 else 'khong doi'})."
    )
    lines.append(
        f"- **Data Corruption gay sut giam Token F1**: {f1_drop:+.4f}."
    )
    lines.append(
        f"- **Sau Idempotent Repair, Hit Rate phuc hoi ve muc baseline**: {_status_badge(hit_rate_recovered)}."
    )
    lines.append(
        f"- **Sau Idempotent Repair, Token F1 phuc hoi ve muc baseline**: {_status_badge(f1_recovered)}."
    )
    lines.append(
        f"- **Data Quality Gate sau phuc hoi**: {_status_badge(bool(repaired_quality.get('success')))}."
    )
    lines.append("")

    write_text(report_path, "\n".join(lines) + "\n")
