from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text

METRIC_LABELS = {
    "retrieval_hit_rate": "Retrieval Hit Rate",
    "mean_token_f1": "Mean Token F1",
    "judge_accuracy": "Judge Accuracy",
    "mean_judge_score": "Mean Judge Score (1-5)",
}


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _delta_pct(baseline: float, other: float) -> str:
    if not baseline:
        return "n/a"
    delta = (other - baseline) / baseline * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}%"


def _quality_section(quality: dict[str, Any]) -> str:
    lines = [
        f"- Trang thai tong: **{'PASS' if quality.get('success') else 'FAIL'}**",
        f"- So dong kiem tra: {quality.get('row_count', 'n/a')}",
        "",
        "| Expectation | Cot | Ket qua |",
        "| :--- | :--- | :---: |",
    ]
    for exp in quality.get("expectations", []):
        config = exp.get("expectation_config", {})
        exp_type = config.get("type", "unknown")
        column = config.get("kwargs", {}).get("column", "-")
        status = "PASS" if exp.get("success") else "FAIL"
        lines.append(f"| `{exp_type}` | `{column}` | {status} |")
    return "\n".join(lines)


def _freshness_section(freshness: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"- Nguong stale: > {freshness.get('threshold_days', 'n/a')} ngay",
            f"- Bai bao stale: {freshness.get('stale_rows', 'n/a')} / {freshness.get('total_rows', 'n/a')}"
            f" ({_pct(freshness.get('stale_ratio', 0.0))})",
            f"- Xuat ban moi nhat: {freshness.get('latest_published', 'n/a')}",
            f"- Xuat ban cu nhat: {freshness.get('oldest_published', 'n/a')}",
            f"- **is_fresh = {freshness.get('is_fresh')}**",
        ]
    )


def _metrics_table(metrics: dict[str, Any]) -> str:
    lines = ["| Metric | Gia tri |", "| :--- | :---: |"]
    for key, label in METRIC_LABELS.items():
        if key not in metrics:
            continue
        value = metrics[key]
        formatted = _pct(value) if key in {"retrieval_hit_rate", "judge_accuracy"} else f"{value:.3f}"
        lines.append(f"| {label} | {formatted} |")
    lines.insert(0, f"- Samples: {metrics.get('samples', 'n/a')}")
    return "\n".join(lines)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Sinh bao cao markdown cho baseline phase (Phase 1)."""
    markdown = f"""# Phase 1 Baseline Report

_Sinh tu dong luc {now_utc().isoformat()}._

## 1. Nguon du lieu

- Nguon: {source_summary.get('source_api', 'n/a')}
- Tong so ban ghi: {source_summary.get('total_records', 'n/a')}
- Truy van: {source_summary.get('query', 'n/a')}

## 2. Ket qua Retrieval & Evaluation (Baseline)

{_metrics_table(metrics)}

## 3. Data Quality Gate (Great Expectations 1.x)

{_quality_section(quality)}

## 4. Freshness SLA

{_freshness_section(freshness)}
"""
    write_text(report_path, markdown)


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
    """Sinh bao cao markdown doi chieu 3 trang thai: Baseline vs Corrupted vs Repaired."""
    comparison_lines = [
        "| Metric | Baseline | Corrupted (Delta) | Repaired (Delta) |",
        "| :--- | :---: | :---: | :---: |",
    ]
    for key, label in METRIC_LABELS.items():
        if key not in baseline_metrics:
            continue
        base = baseline_metrics[key]
        corrupted = corrupted_metrics.get(key, 0.0)
        repaired = repaired_metrics.get(key, 0.0)
        is_ratio = key in {"retrieval_hit_rate", "judge_accuracy"}
        fmt = _pct if is_ratio else (lambda v: f"{v:.3f}")
        comparison_lines.append(
            f"| {label} | {fmt(base)} | {fmt(corrupted)} ({_delta_pct(base, corrupted)}) |"
            f" {fmt(repaired)} ({_delta_pct(base, repaired)}) |"
        )

    markdown = f"""# Corruption & Repair Comparison Report

_Sinh tu dong luc {now_utc().isoformat()}._

## 1. So sanh Retrieval & Evaluation: Baseline vs Corrupted vs Repaired

{chr(10).join(comparison_lines)}

## 2. Data Quality Gate — Corrupted

{_quality_section(corrupted_quality)}

## 3. Data Quality Gate — Repaired

{_quality_section(repaired_quality)}

## 4. Freshness SLA — Corrupted

{_freshness_section(corrupted_freshness)}

## 5. Freshness SLA — Repaired

{_freshness_section(repaired_freshness)}

## 6. Ket luan

- Corruption lam giam Retrieval Hit Rate {_delta_pct(baseline_metrics.get('retrieval_hit_rate', 0.0), corrupted_metrics.get('retrieval_hit_rate', 0.0))}
  va Mean Token F1 {_delta_pct(baseline_metrics.get('mean_token_f1', 0.0), corrupted_metrics.get('mean_token_f1', 0.0))} so voi Baseline.
- Idempotent Repair (nap lai tu raw snapshot) dua Retrieval Hit Rate ve {_delta_pct(baseline_metrics.get('retrieval_hit_rate', 0.0), repaired_metrics.get('retrieval_hit_rate', 0.0))}
  va Mean Token F1 ve {_delta_pct(baseline_metrics.get('mean_token_f1', 0.0), repaired_metrics.get('mean_token_f1', 0.0))} so voi Baseline.
"""
    write_text(report_path, markdown)
