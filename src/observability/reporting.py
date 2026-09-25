from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text

# Metric keys produced by evaluation.metrics.evaluate_pipeline (summary dict).
METRIC_ROWS: list[tuple[str, str]] = [
    ("retrieval_hit_rate", "Retrieval Hit Rate"),
    ("mean_token_f1", "Mean Token F1"),
    ("judge_accuracy", "LLM Judge Accuracy"),
    ("mean_judge_score", "Mean LLM Judge Score"),
]


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "✅ PASS" if value else "❌ FAIL"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _delta(new: Any, base: Any) -> str:
    if not isinstance(new, (int, float)) or not isinstance(base, (int, float)) or isinstance(new, bool):
        return "n/a"
    return f"{new - base:+.4f}"


def _metrics_table(metrics: dict[str, Any]) -> list[str]:
    lines = ["| Metric | Value |", "| :--- | ---: |", f"| Samples | {_fmt(metrics.get('samples'))} |"]
    lines += [f"| {label} | {_fmt(metrics.get(key))} |" for key, label in METRIC_ROWS]
    return lines


def _ragas_lines(metrics: dict[str, Any]) -> list[str]:
    ragas = metrics.get("ragas")
    if not isinstance(ragas, dict) or not ragas:
        return []
    if "error" in ragas:
        return [f"- RAGAS: skipped ({ragas['error']})"]
    return [f"- RAGAS `{key}`: {_fmt(value)}" for key, value in ragas.items()]


def _quality_lines(quality: dict[str, Any]) -> list[str]:
    """Expected shape: {"success": bool, "results": [{"expectation", "column", "success", "observed"?}]}."""
    lines = [f"**Overall Quality Gate:** {_fmt(quality.get('success'))}", ""]
    results = quality.get("results") or []
    if results:
        lines += ["| Expectation | Column | Status | Observed |", "| :--- | :--- | :---: | :--- |"]
        for item in results:
            lines.append(
                f"| `{item.get('expectation', '?')}` | {item.get('column') or '-'} "
                f"| {_fmt(item.get('success'))} | {_fmt(item.get('observed'))} |"
            )
    return lines


def _freshness_lines(freshness: dict[str, Any]) -> list[str]:
    keys = [
        ("is_fresh", "Is fresh"),
        ("total_rows", "Total rows"),
        ("stale_rows", "Stale rows (age_days > threshold)"),
        ("stale_ratio", "Stale ratio"),
        ("latest_published", "Latest published"),
        ("oldest_published", "Oldest published"),
    ]
    lines = ["| Field | Value |", "| :--- | :--- |"]
    lines += [f"| {label} | {_fmt(freshness.get(key))} |" for key, label in keys if key in freshness]
    return lines


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    lines = [
        "# Phase 1 Report — Baseline Pipeline",
        "",
        f"_Generated at {now_utc().isoformat(timespec='seconds')}_",
        "",
        "## 1. Source Summary",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in source_summary.items()]
    lines += ["", "## 2. Retrieval & Answer Evaluation", "", *_metrics_table(metrics)]
    ragas = _ragas_lines(metrics)
    if ragas:
        lines += ["", *ragas]
    lines += ["", "## 3. Data Quality Gate (Great Expectations 1.x)", "", *_quality_lines(quality)]
    lines += ["", "## 4. Freshness SLA", "", *_freshness_lines(freshness), ""]
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
    lines = [
        "# Corruption Report — Baseline vs Corrupted vs Repaired",
        "",
        f"_Generated at {now_utc().isoformat(timespec='seconds')}_",
        "",
        "## 1. Evaluation Metrics (3 states)",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in METRIC_ROWS:
        base, bad, fixed = baseline_metrics.get(key), corrupted_metrics.get(key), repaired_metrics.get(key)
        lines.append(
            f"| {label} | {_fmt(base)} | {_fmt(bad)} | {_fmt(fixed)} | {_delta(bad, base)} | {_delta(fixed, base)} |"
        )

    lines += [
        "",
        "## 2. Observability Signals",
        "",
        "| Signal | Corrupted | Repaired |",
        "| :--- | :---: | :---: |",
        f"| Quality Gate (GX 1.x) | {_fmt(corrupted_quality.get('success'))} | {_fmt(repaired_quality.get('success'))} |",
        f"| Freshness SLA | {_fmt(corrupted_freshness.get('is_fresh'))} | {_fmt(repaired_freshness.get('is_fresh'))} |",
        f"| Stale ratio | {_fmt(corrupted_freshness.get('stale_ratio'))} | {_fmt(repaired_freshness.get('stale_ratio'))} |",
        f"| Row count | {_fmt(corrupted_freshness.get('total_rows'))} | {_fmt(repaired_freshness.get('total_rows'))} |",
    ]

    failed = [item for item in corrupted_quality.get("results") or [] if not item.get("success")]
    lines += ["", "### Expectations failed on corrupted data", ""]
    if failed:
        lines += [f"- `{item.get('expectation')}` on `{item.get('column') or 'table'}`" for item in failed]
    else:
        lines.append("- None — the quality gate did NOT catch the corruption (silent failure risk).")

    lines += ["", "## 3. Analysis", ""]
    lines += _analysis(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, corrupted_freshness)
    lines.append("")
    write_text(report_path, "\n".join(lines))


def _analysis(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
    corrupted_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
) -> list[str]:
    """Derive the narrative from actual numbers so the report never states unsupported claims."""
    lines: list[str] = []
    for key, label in METRIC_ROWS:
        base, bad, fixed = baseline.get(key), corrupted.get(key), repaired.get(key)
        if not all(isinstance(v, (int, float)) for v in (base, bad, fixed)):
            continue
        degraded = "dropped" if bad < base else "did not drop"
        recovered = "fully recovered" if abs(fixed - base) < 1e-9 else ("partially recovered" if fixed > bad else "did not recover")
        lines.append(f"- **{label}** {degraded} ({_fmt(base)} → {_fmt(bad)}) and {recovered} after repair ({_fmt(fixed)}).")

    gate = corrupted_quality.get("success")
    fresh = corrupted_freshness.get("is_fresh")
    lines.append(
        f"- Quality gate on corrupted data: {'caught the corruption' if gate is False else 'did not fail'}; "
        f"freshness SLA: {'raised a stale alert' if fresh is False else 'reported fresh'}."
    )
    return lines
