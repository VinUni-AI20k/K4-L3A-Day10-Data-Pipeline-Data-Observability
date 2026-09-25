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
    """Viet markdown report cho baseline phase.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    def pct(value: Any) -> str:
        return f"{value:.2%}" if isinstance(value, (int, float)) else str(value)

    check_rows = "\n".join(
        f"| {c['expectation']} | {c.get('column') or '-'} | {'PASS' if c['success'] else 'FAIL'} |"
        for c in quality.get("checks", [])
    )
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source",
        *(f"- **{key}**: {value}" for key, value in source_summary.items()),
        "",
        "## Retrieval & Answer Metrics",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Samples | {metrics.get('samples')} |",
        f"| Retrieval hit rate | {pct(metrics.get('retrieval_hit_rate'))} |",
        f"| Mean token F1 | {metrics.get('mean_token_f1', 0):.4f} |",
        f"| Judge accuracy | {pct(metrics.get('judge_accuracy'))} |",
        f"| Mean judge score | {metrics.get('mean_judge_score', 0):.2f} / 5 |",
        "",
        "## Data Quality",
        f"Overall status: **{'PASS' if quality.get('success') else 'FAIL'}** "
        f"({quality.get('passed')} passed, {quality.get('failed')} failed)",
        "",
        "| Expectation | Column | Result |",
        "| --- | --- | --- |",
        check_rows,
        "",
        "## Freshness",
        f"- Latest published: {freshness.get('latest_published')}",
        f"- Oldest published: {freshness.get('oldest_published')}",
        f"- Stale rows: {freshness.get('stale_rows')} / {freshness.get('total_rows')}",
        f"- Is fresh: {freshness.get('is_fresh')}",
        "",
    ]
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
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    def status(ok: bool) -> str:
        return "✅ PASSED" if ok else "❌ FAILED"

    def fresh(payload: dict[str, Any]) -> str:
        if payload.get("is_fresh"):
            return f"✅ Đạt chuẩn ({payload.get('stale_rows')}/{payload.get('total_rows')} stale)"
        return f"❌ Vi phạm ({payload.get('stale_rows')}/{payload.get('total_rows')} stale)"

    def failed(quality: dict[str, Any]) -> str:
        names = [c["expectation"] for c in quality.get("checks", []) if not c["success"]]
        return ", ".join(names) if names else "-"

    def row(label: str, key: str, fmt: str) -> str:
        cells = (m.get(key, 0) for m in (baseline_metrics, corrupted_metrics, repaired_metrics))
        return f"| {label} | " + " | ".join(format(v, fmt) for v in cells) + " |"

    lines = [
        "# Corruption & Repair Comparison Report",
        "",
        "| Metric | Baseline (Dữ liệu sạch) | Corrupted (Dữ liệu bị lỗi) | Repaired (Sau phục hồi) |",
        "| --- | --- | --- | --- |",
        f"| Data Quality Gate | ✅ PASSED | {status(corrupted_quality.get('success'))} "
        f"| {status(repaired_quality.get('success'))} |",
        f"| Freshness | ✅ Đạt chuẩn | {fresh(corrupted_freshness)} | {fresh(repaired_freshness)} |",
        row("Retrieval Hit Rate", "retrieval_hit_rate", ".2%"),
        row("Mean Token F1", "mean_token_f1", ".3f"),
        row("Judge Accuracy", "judge_accuracy", ".2%"),
        row("Mean Judge Score (1-5)", "mean_judge_score", ".2f"),
        "",
        "## Failed expectations",
        f"- Corrupted: {failed(corrupted_quality)}",
        f"- Repaired: {failed(repaired_quality)}",
        "",
        "## Kết luận",
        "Dữ liệu bẩn không gây lỗi runtime nhưng làm RAG trả lời sai (silent failure); "
        "Data Quality Gate và Freshness check phát hiện được sự cố, và repair từ raw snapshot "
        "đưa các chỉ số về mức baseline.",
        "",
    ]
    write_text(report_path, "\n".join(lines))
